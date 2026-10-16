// m3d_route: router for the M3D routing challenge.
//
// Input: one m3d-instance JSON. Output: one m3d-submission JSON.
//   m3d_route --instance X.json --out Y.sol.json --time-limit S --seed N --threads T
//             [--set key=value ...]
//
// Phases
//   A1  negotiated congestion (PathFinder) until no grid point is shared by two nets;
//   A2  exact per-net reroute: rip one net, route its true-delay shortest-path tree with
//       every other net fixed (optimal for that net), sweep until a pass improves nothing.
//
// The objective is the sum over sinks of each sink's driver-to-sink path delay. A net
// alone is best routed as a shortest-path tree, so every per-net route here is the tree of
// a single-source shortest-path search from the driver (predecessor pointers), cut to the
// paths that reach sinks.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "json.hpp"

using Clock = std::chrono::steady_clock;

// --------------------------------------------------------------------------------------
// Options: --set key=value. Every key must be read, so typos fail loudly.
// --------------------------------------------------------------------------------------
struct Options {
  std::map<std::string, std::string> kv;
  std::set<std::string> used;

  double get(const std::string& k, double dflt) {
    used.insert(k);
    auto it = kv.find(k);
    return it == kv.end() ? dflt : std::stod(it->second);
  }
  std::string get_str(const std::string& k, const std::string& dflt) {
    used.insert(k);
    auto it = kv.find(k);
    return it == kv.end() ? dflt : it->second;
  }
  long long get_int(const std::string& k, long long dflt) {
    used.insert(k);
    auto it = kv.find(k);
    return it == kv.end() ? dflt : std::stoll(it->second);
  }
  void check_unused() const {
    for (const auto& [k, v] : kv)
      if (!used.count(k)) {
        std::cerr << "unknown --set key: " << k << "\n";
        std::exit(2);
      }
  }
};

// --------------------------------------------------------------------------------------
// Instance
// --------------------------------------------------------------------------------------
struct Instance {
  std::string name;
  int W = 0, H = 0, L = 0;
  std::vector<int> ld;
  int via = 0;
  std::vector<int> net_id;              // external id per net index
  std::vector<int> drv;                 // driver vertex per net
  std::vector<std::vector<int>> sinks;  // sink vertices per net
};

static Instance load_instance(const std::string& path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) throw std::runtime_error("cannot open " + path);
  std::stringstream ss;
  ss << f.rdbuf();
  mj::Value j = mj::parse(ss.str());
  Instance in;
  in.name = j.at("name").str;
  in.W = static_cast<int>(j.at("grid").at("width").as_int());
  in.H = static_cast<int>(j.at("grid").at("height").as_int());
  in.L = static_cast<int>(j.at("grid").at("layers").as_int());
  for (const auto& d : j.at("delay").at("layer_delay").arr) in.ld.push_back(static_cast<int>(d.as_int()));
  in.via = static_cast<int>(j.at("delay").at("via_delay").as_int());
  std::map<long long, int> pin_vertex;
  for (const auto& p : j.at("pins").arr) {
    long long x = p.at("x").as_int(), y = p.at("y").as_int(), z = p.at("z").as_int();
    pin_vertex[p.at("id").as_int()] = static_cast<int>((z * in.H + y) * in.W + x);
  }
  for (const auto& n : j.at("nets").arr) {
    in.net_id.push_back(static_cast<int>(n.at("id").as_int()));
    in.drv.push_back(pin_vertex.at(n.at("driver").as_int()));
    std::vector<int> s;
    for (const auto& k : n.at("sinks").arr) s.push_back(pin_vertex.at(k.as_int()));
    in.sinks.push_back(std::move(s));
  }
  return in;
}

// --------------------------------------------------------------------------------------
// Router
// --------------------------------------------------------------------------------------
class Router {
 public:
  Router(const Instance& in, Options& opt, uint64_t seed, Clock::time_point start, Clock::time_point deadline)
      : in_(in), rng_(seed), start_(start), deadline_(deadline) {
    W = in.W; H = in.H; L = in.L; WH = W * H; N = WH * L;
    via = in.via;
    maxc = via;
    for (int z = 0; z < L; ++z) maxc = std::max(maxc, in.ld[z]);
    nn = static_cast<int>(in.drv.size());

    pf0_ = opt.get("neg_pres0", 0.2);
    pf_mult_ = opt.get("neg_pres_mult", 1.03);
    hist_fac_ = opt.get("neg_hist", 0.1);
    // Escalation: past these fractions of the budget, present-cost growth switches to the
    // fast factors so a legal solution exists before the deadline.
    esc1_ = opt.get("neg_esc1", 0.35);
    esc2_ = opt.get("neg_esc2", 0.6);
    max_moves_ = opt.get_int("max_iters", -1);
    lns_ = static_cast<int>(opt.get_int("lns", 0));
    lns_k_ = static_cast<int>(opt.get_int("lns_k", 4));
    lns_order_ = static_cast<int>(opt.get_int("lns_order", 1));
    // B6: annealed acceptance in the LNS; temperature falls geometrically from sa_t0 to
    // sa_t1 over the LNS phase. sa_t0 = 0 keeps accept-if-not-worse.
    sa_t0_ = opt.get("sa_t0", 0.0);
    sa_t1_ = opt.get("sa_t1", 0.05);
    // B8: negotiated group repair. Up to gneg rounds of PathFinder among the ripped group
    // (everything else fixed); if the group ends overlap-free, polish each net with an exact
    // reroute; otherwise fall back to sequential exact routing.
    gneg_ = static_cast<int>(opt.get_int("gneg", 0));
    // C1: LNS searches stay inside the group's old-tree bounding box expanded by lns_win
    // (-1 = whole grid). The old trees fit inside, so a move can always restore them.
    lns_win_ = static_cast<int>(opt.get_int("lns_win", -1));
    gneg_pf0_ = opt.get("gneg_pf0", 0.5);
    gneg_mult_ = opt.get("gneg_mult", 2.0);
    gneg_hist_ = opt.get("gneg_hist", 0.5);
    // after the first round, reroute only group nets that touch an overused point
    gneg_sel_ = static_cast<int>(opt.get_int("gneg_sel", 0));
    // B2: a net with k sinks sees congestion costs scaled by k^-fan_alpha in negotiation, so
    // big nets (one trunk serving many sinks) keep the cheap layers and small nets yield.
    fan_alpha_ = opt.get("fan_alpha", 0.0);
    // E1: neighborhood portfolio. 0 = ideal-tree blockers only (B1); 1 = roulette between B1
    // and a window neighborhood (target net + nets with points in a box of half-size lns_wr
    // around a random point of the target's congestion-free tree). Weights track delay
    // gained per microsecond with reaction rate lns_gamma.
    lns_mix_ = static_cast<int>(opt.get_int("lns_mix", 0));
    lns_wr_ = static_cast<int>(opt.get_int("lns_wr", 3));
    lns_gamma_ = opt.get("lns_gamma", 0.01);
    // Idea 1: negotiated trees grow one sink at a time; points already in the net's tree start
    // at their true delay and pay no congestion again, so a shared trunk is charged once.
    // 1 = everywhere, 2 = initial negotiation only (group moves keep shortest-path trees).
    tree_seq_ = static_cast<int>(opt.get_int("tree_seq", 0));
    // Idea 2: exact reroutes keep every sink's shortest delay but pick, among equally fast
    // routes, the one adding the fewest new points (a fast-layer point counts 1 + tie_mid).
    tie_share_ = static_cast<int>(opt.get_int("tie_share", 0));
    tie_mid_ = static_cast<int>(opt.get_int("tie_mid", 1));
    // Idea 3: threshold acceptance (accept a group up to ta_t0 worse, falling linearly to 0 at
    // the deadline), a bigger "kick" neighborhood after kick_after moves without improvement,
    // and a return to the best solution after restore_after moves without a new best.
    ta_t0_ = opt.get("ta_t0", 0.0);
    kick_after_ = opt.get_int("kick_after", 0);
    kick_k_ = static_cast<int>(opt.get_int("kick_k", 12));
    kick_wr_ = static_cast<int>(opt.get_int("kick_wr", 6));
    restore_after_ = opt.get_int("restore_after", 0);
    // Idea 4: A* for single-sink nets in exact and negotiated searches (exact delays kept).
    astar_ = static_cast<int>(opt.get_int("astar", 0));
    // Idea 5: with --threads T > 1, T LNS workers run from the same solution and every
    // par_sync seconds all adopt the best one.
    par_sync_ = opt.get("par_sync", 2.0);
    verbose_ = opt.get_int("verbose", 0);
    // Diagnostics only (off by default): write the current routes to snap_dir/snap_NNNN.sol.json
    // every snap_neg negotiation rounds, after each A2 sweep and every snap_s seconds of LNS,
    // with one line per snapshot in snap_dir/index.jsonl. Used for animations.
    snap_dir_ = opt.get_str("snap_dir", "");
    snap_s_ = opt.get("snap_s", 1.0);
    snap_neg_ = static_cast<int>(opt.get_int("snap_neg", 5));

    X.resize(N); Y.resize(N); Z.resize(N);
    for (int v = 0; v < N; ++v) {
      Z[v] = static_cast<int16_t>(v / WH);
      int r = v % WH;
      Y[v] = static_cast<int16_t>(r / W);
      X[v] = static_cast<int16_t>(r % W);
    }
    pin_net.assign(N, -1);
    for (int n = 0; n < nn; ++n) {
      pin_net[in.drv[n]] = n;
      for (int s : in.sinks[n]) pin_net[s] = n;
    }
    owner.assign(N, -1);
    occ.assign(N, 0);
    hist.assign(N, 0.0);
    dist.assign(N, 0);
    fdist.assign(N, 0.0);
    pred.assign(N, -1);
    seen.assign(N, 0);
    done.assign(N, 0);
    target.assign(N, 0);
    intree.assign(N, 0);
    dly.assign(N, 0);
    buckets.resize(maxc + 1);
    minld_ = *std::min_element(in.ld.begin(), in.ld.end());
    fast_.assign(L, 0);
    for (int z = 0; z < L; ++z) fast_[z] = in.ld[z] == minld_;
    inT_.assign(N, 0); sinkm_.assign(N, 0); rseen_.assign(N, 0); rdone_.assign(N, 0);
    rcost_.assign(N, 0); rnext_.assign(N, -1);
    abuckets_.resize(maxc + std::max(minld_, via) + 2);
    tv.resize(nn); tp.resize(nn);
    netw_.resize(nn);
    for (int n = 0; n < nn; ++n) netw_[n] = std::pow(static_cast<double>(in.sinks[n].size()), -fan_alpha_);
    delay.assign(nn, 0);
  }

  // ---- A1: negotiated congestion --------------------------------------------------
  bool negotiate() {
    std::vector<int> order(nn);
    std::iota(order.begin(), order.end(), 0);
    std::vector<int> bbox(nn);
    for (int n = 0; n < nn; ++n) {
      int x0 = X[in_.drv[n]], x1 = x0, y0 = Y[in_.drv[n]], y1 = y0, z0 = Z[in_.drv[n]], z1 = z0;
      for (int s : in_.sinks[n]) {
        x0 = std::min<int>(x0, X[s]); x1 = std::max<int>(x1, X[s]);
        y0 = std::min<int>(y0, Y[s]); y1 = std::max<int>(y1, Y[s]);
        z0 = std::min<int>(z0, Z[s]); z1 = std::max<int>(z1, Z[s]);
      }
      bbox[n] = (x1 - x0) + (y1 - y0) + (z1 - z0);
    }
    std::stable_sort(order.begin(), order.end(), [&](int a, int b) { return bbox[a] > bbox[b]; });

    double pf = pf0_;
    for (int n : order) {
      if (!route_neg(n, pf)) return false;
      add_occ(n);
    }
    std::vector<int> over;
    std::vector<char> affected(nn);
    for (neg_iters_ = 1;; ++neg_iters_) {
      over.clear();
      for (int v = 0; v < N; ++v)
        if (occ[v] > 1) over.push_back(v);
      if (verbose_) std::cerr << "neg iter " << neg_iters_ << " overused " << over.size() << "\n";
      if (!snap_dir_.empty() && (neg_iters_ == 1 || neg_iters_ % snap_neg_ == 0 || over.empty()))
        snapshot(over.empty() ? "legal" : "negotiate", static_cast<long long>(over.size()));
      if (over.empty()) break;
      if (Clock::now() > deadline_) return false;
      for (int v : over) hist[v] += hist_fac_ * (occ[v] - 1);
      double frac = std::chrono::duration<double>(Clock::now() - start_).count() /
                    std::chrono::duration<double>(deadline_ - start_).count();
      double mult = frac > esc2_ ? 3.0 : frac > esc1_ ? 1.7 : pf_mult_;
      pf = std::min(pf * mult, 1e6);
      std::fill(affected.begin(), affected.end(), 0);
      for (int n = 0; n < nn; ++n)
        for (int v : tv[n])
          if (occ[v] > 1) { affected[n] = 1; break; }
      for (int n : order) {
        if (!affected[n]) continue;
        sub_occ(n);
        if (!route_neg(n, pf)) return false;
        add_occ(n);
      }
    }
    // Legal: every vertex has at most one net.
    total_ = 0;
    for (int n = 0; n < nn; ++n) {
      for (int v : tv[n]) owner[v] = n;
      total_ += delay[n];
    }
    for (int v = 0; v < N; ++v)
      if (pin_net[v] >= 0) owner[v] = pin_net[v];
    return true;
  }

  // ---- A2: exact per-net reroute ----------------------------------------------------
  void refine() {
    std::vector<int> order(nn);
    std::iota(order.begin(), order.end(), 0);
    while (Clock::now() < deadline_) {
      std::shuffle(order.begin(), order.end(), rng_);
      int improved = 0;
      bool stop = false;
      for (int n : order) {
        if (Clock::now() >= deadline_ || (max_moves_ >= 0 && moves_ >= max_moves_)) { stop = true; break; }
        long long old = delay[n];
        rip(n);
        bool ok = route_exact(n);
        if (!ok) { std::cerr << "internal error: exact reroute failed\n"; std::exit(3); }
        place(n);
        total_ += delay[n] - old;
        ++moves_;
        if (delay[n] < old) ++improved;
      }
      ++sweeps_;
      snapshot("refine", 0);
      if (verbose_) std::cerr << "sweep " << sweeps_ << " improved " << improved << " total " << total_ << "\n";
      if (stop || improved == 0) break;
    }
  }

  // ---- B1: excess-targeted neighborhood search ----------------------------------------
  // Pick a net with probability proportional to its excess over its congestion-free delay;
  // the group is that net plus up to lns_k-1 nets sitting on its congestion-free tree. Rip
  // the group, reroute exact shortest-path trees (target first, the rest in random order),
  // keep the result if the group's total delay did not rise.
  void lns() {
    if (!lns_) return;
    lns_setup();
    lns_run(deadline_);
    lns_finish();
  }

  void lns_setup() {
    ideal_v.resize(nn);
    ideal_d.assign(nn, 0);
    std::vector<int> tmpP;
    for (int n = 0; n < nn; ++n) {
      route_exact<true>(n);
      ideal_d[n] = build_tree_into(n, ideal_v[n], tmpP);
    }
    std::fill(occ.begin(), occ.end(), 0);
    std::fill(hist.begin(), hist.end(), 0.0);
    net_mark_.assign(nn, 0);
    int kmax = std::max(lns_k_, kick_after_ > 0 ? kick_k_ : 0);
    old_v_.resize(kmax); old_p_.resize(kmax); old_d_.resize(kmax);
    cum_.resize(nn);
    track_best_ = sa_t0_ > 0 || ta_t0_ > 0;
    best_total_ = total_;
    if (track_best_) { best_v_ = tv; best_p_ = tp; best_d_ = delay; }
    lns_start_ = Clock::now();
    lns_span_ = std::max(1e-3, std::chrono::duration<double>(deadline_ - lns_start_).count());
    temp_ = sa_t0_;
    thr_ = ta_t0_;
  }

  // Runs LNS moves until `until`; returns false if no net has any excess left.
  bool lns_run(Clock::time_point until) {
    std::uniform_real_distribution<double> unif(0.0, 1.0);
    while (true) {
      auto now = Clock::now();
      if (now >= until || (max_moves_ >= 0 && moves_ >= max_moves_)) break;
      if (!snap_dir_.empty() && std::chrono::duration<double>(now - last_snap_).count() >= snap_s_)
        snapshot("search", 0);
      if ((sa_t0_ > 0 || ta_t0_ > 0) && (moves_ & 63) == 0) {
        double frac = std::min(1.0, std::chrono::duration<double>(now - lns_start_).count() / lns_span_);
        if (sa_t0_ > 0) temp_ = sa_t0_ * std::pow(sa_t1_ / sa_t0_, frac);
        if (ta_t0_ > 0) thr_ = ta_t0_ * (1.0 - frac);
      }
      if (restore_after_ > 0 && track_best_ && since_best_ >= restore_after_ && total_ > best_total_) {
        restore_best();
        since_best_ = 0;
      }
      double acc = 0;
      for (int n = 0; n < nn; ++n) {
        acc += static_cast<double>(delay[n] - ideal_d[n]);
        cum_[n] = acc;
      }
      if (acc <= 0) return false;
      double r = std::uniform_real_distribution<double>(0.0, acc)(rng_);
      int t = static_cast<int>(std::upper_bound(cum_.begin(), cum_.end(), r) - cum_.begin());
      if (t >= nn) t = nn - 1;
      ++epoch_;
      net_mark_[t] = epoch_;
      cand_.clear();
      bool kick = kick_after_ > 0 && since_imp_ >= kick_after_;
      if (kick) since_imp_ = 0;
      int heur = 0;
      if (kick) heur = 1;
      else if (lns_mix_) heur = unif(rng_) * (hw_[0] + hw_[1]) < hw_[0] ? 0 : 1;
      const int wr = kick ? kick_wr_ : lns_wr_;
      const int kk = kick ? kick_k_ : lns_k_;
      auto move_t0 = Clock::now();
      if (heur == 0) {
        for (int v : ideal_v[t]) {
          int o = owner[v];
          if (o >= 0 && net_mark_[o] != epoch_) { net_mark_[o] = epoch_; cand_.push_back(o); }
        }
      } else {
        int c = ideal_v[t][std::uniform_int_distribution<size_t>(0, ideal_v[t].size() - 1)(rng_)];
        int cx = X[c], cy = Y[c];
        for (int z = 0; z < L; ++z)
          for (int y = std::max(0, cy - wr); y <= std::min(H - 1, cy + wr); ++y)
            for (int x = std::max(0, cx - wr); x <= std::min(W - 1, cx + wr); ++x) {
              int o = owner[(z * H + y) * W + x];
              if (o >= 0 && net_mark_[o] != epoch_) { net_mark_[o] = epoch_; cand_.push_back(o); }
            }
      }
      std::shuffle(cand_.begin(), cand_.end(), rng_);
      if (static_cast<int>(cand_.size()) > kk - 1) cand_.resize(kk - 1);
      auto& group = group_;
      group.clear();
      group.push_back(t);
      group.insert(group.end(), cand_.begin(), cand_.end());
      if (lns_order_ == 1) std::shuffle(group.begin(), group.end(), rng_);
      long long old_sum = 0;
      for (size_t i = 0; i < group.size(); ++i) {
        int n = group[i];
        old_v_[i] = tv[n]; old_p_[i] = tp[n]; old_d_[i] = delay[n];
        old_sum += delay[n];
        rip(n);
      }
      if (lns_win_ >= 0) {
        wx0_ = W; wx1_ = -1; wy0_ = H; wy1_ = -1;
        for (size_t i = 0; i < group.size(); ++i)
          for (int v : old_v_[i]) {
            wx0_ = std::min<int>(wx0_, X[v]); wx1_ = std::max<int>(wx1_, X[v]);
            wy0_ = std::min<int>(wy0_, Y[v]); wy1_ = std::max<int>(wy1_, Y[v]);
          }
        wx0_ = std::max(0, wx0_ - lns_win_); wx1_ = std::min(W - 1, wx1_ + lns_win_);
        wy0_ = std::max(0, wy0_ - lns_win_); wy1_ = std::min(H - 1, wy1_ + lns_win_);
      }
      long long new_sum = 0;
      size_t routed = 0;
      if (gneg_ > 0 && group_negotiate(group)) {
        for (int n : group) place(n);
        for (int n : group) {
          rip(n);
          route_exact(n);  // cannot fail: the negotiated tree is still available
          place(n);
          new_sum += delay[n];
        }
        routed = group.size();
      } else {
        for (; routed < group.size(); ++routed) {
          int n = group[routed];
          if (!route_exact(n)) break;
          place(n);
          new_sum += delay[n];
        }
      }
      ++moves_;
      ++since_imp_;
      ++since_best_;
      wx0_ = 0; wx1_ = 1 << 30; wy0_ = 0; wy1_ = 1 << 30;
      if (lns_mix_ && !kick) {
        double us = std::max(1.0, std::chrono::duration<double, std::micro>(Clock::now() - move_t0).count());
        double gain = routed == group.size() && new_sum < old_sum ? static_cast<double>(old_sum - new_sum) : 0.0;
        hw_[heur] = std::max(1e-4, (1 - lns_gamma_) * hw_[heur] + lns_gamma_ * gain / us);
        ++hcount_[heur];
      }
      if (routed == group.size() &&
          (new_sum <= old_sum || (sa_t0_ > 0 && unif(rng_) < std::exp(-(new_sum - old_sum) / temp_)) ||
           (ta_t0_ > 0 && static_cast<double>(new_sum - old_sum) <= thr_))) {
        total_ += new_sum - old_sum;
        ++lns_accepted_;
        if (new_sum < old_sum) since_imp_ = 0;
        if (track_best_ && total_ < best_total_) {
          best_total_ = total_;
          best_v_ = tv; best_p_ = tp; best_d_ = delay;
          since_best_ = 0;
        }
        continue;
      }
      for (size_t i = 0; i < routed; ++i) rip(group[i]);
      for (size_t i = 0; i < group.size(); ++i) {
        int n = group[i];
        tv[n].swap(old_v_[i]); tp[n].swap(old_p_[i]); delay[n] = old_d_[i];
        place(n);
      }
    }
    return true;
  }

  void restore_best() {
    for (int n = 0; n < nn; ++n) rip(n);
    tv = best_v_; tp = best_p_; delay = best_d_;
    for (int n = 0; n < nn; ++n) place(n);
    total_ = best_total_;
  }

  void lns_finish() {
    if (track_best_ && total_ > best_total_) restore_best();
    if (verbose_)
      std::cerr << "lns moves " << moves_ << " accepted " << lns_accepted_ << " total " << total_ << " heur "
                << hcount_[0] << "/" << hcount_[1] << " w " << hw_[0] << "/" << hw_[1] << "\n";
  }

  // Idea 5 helpers: a worker ends an epoch on its best solution, then adopts the overall best.
  void epoch_end() {
    if (track_best_ && total_ > best_total_) restore_best();
    best_total_ = total_;
    if (track_best_) { best_v_ = tv; best_p_ = tp; best_d_ = delay; }
  }
  void adopt(const Router& o) {
    tv = o.tv; tp = o.tp; delay = o.delay; owner = o.owner; total_ = o.total_;
    best_total_ = total_;
    if (track_best_) { best_v_ = tv; best_p_ = tp; best_d_ = delay; }
    since_best_ = 0; since_imp_ = 0;
  }
  void reseed(uint64_t s) { rng_.seed(s); }
  void quiet() { snap_dir_.clear(); verbose_ = 0; }
  void add_moves(long long m) { moves_ += m; }
  bool lns_enabled() const { return lns_ != 0; }
  double par_sync() const { return par_sync_; }
  Clock::time_point deadline() const { return deadline_; }

  // PathFinder among the (ripped) group with every other net fixed. Returns true if the
  // group's trees end pairwise disjoint (trees left in tv/tp, not placed). occ and hist are
  // back to zero on return.
  bool group_negotiate(const std::vector<int>& group) {
    double pf = gneg_pf0_;
    bool ok = true, legal = false;
    gaff_.assign(group.size(), 1);
    for (int round = 0; round < gneg_ && ok; ++round) {
      for (size_t i = 0; i < group.size(); ++i) {
        int n = group[i];
        if (round > 0 && gneg_sel_ && !gaff_[i]) continue;
        if (round > 0) sub_occ(n);
        if (!route_neg<true>(n, pf)) { ok = false; break; }
        add_occ(n);
      }
      if (!ok) break;
      bool over = false;
      for (size_t i = 0; i < group.size(); ++i) {
        gaff_[i] = 0;
        for (int v : tv[group[i]])
          if (occ[v] > 1) {
            over = true;
            gaff_[i] = 1;
            if (hist[v] == 0.0) touched_.push_back(v);
            hist[v] += gneg_hist_;
          }
      }
      if (!over) { legal = true; break; }
      pf *= gneg_mult_;
    }
    if (ok) {
      for (int n : group) sub_occ(n);
    } else {
      std::fill(occ.begin(), occ.end(), 0);  // rare: cannot happen while old trees are free
    }
    for (int v : touched_) hist[v] = 0.0;
    touched_.clear();
    return ok && legal;
  }

  long long total() const { return total_; }
  long long moves() const { return moves_; }
  int neg_iters() const { return neg_iters_; }

  void write(const std::string& path) const {
    std::string out;
    out.reserve(1 << 20);
    out += "{\"format\": \"m3d-submission\", \"version\": 1, \"instance\": \"";
    out += in_.name;
    out += "\", \"routes\": [";
    char buf[128];
    for (int n = 0; n < nn; ++n) {
      if (n) out += ", ";
      out += "{\"net\": " + std::to_string(in_.net_id[n]) + ", \"edges\": [";
      bool first = true;
      for (size_t i = 0; i < tv[n].size(); ++i) {
        int p = tp[n][i];
        if (p < 0) continue;
        int v = tv[n][i];
        std::snprintf(buf, sizeof buf, "%s[[%d, %d, %d], [%d, %d, %d]]", first ? "" : ", ", X[p], Y[p], Z[p],
                      X[v], Y[v], Z[v]);
        out += buf;
        first = false;
      }
      out += "]}";
    }
    out += "]}\n";
    std::ofstream f(path, std::ios::binary);
    f << out;
    if (!f) throw std::runtime_error("cannot write " + path);
  }

 private:
  const Instance& in_;
  std::mt19937_64 rng_;
  Clock::time_point start_, deadline_;
  int W, H, L, WH, N, via, maxc, nn;
  std::vector<int16_t> X, Y, Z;
  std::vector<int> pin_net;  // net owning the pin at this vertex, or -1
  std::vector<int> owner;    // legal phase: net using this vertex, or -1
  std::vector<int> occ;      // negotiation: number of nets using this vertex
  std::vector<double> hist;  // negotiation: history cost
  // search scratch (stamped so nothing is cleared between searches)
  std::vector<int> dist;
  std::vector<double> fdist;
  std::vector<int> pred;
  std::vector<uint32_t> seen, done, target, intree;
  std::vector<int> dly;
  uint32_t stamp_ = 0;
  std::vector<std::vector<int>> buckets;
  std::vector<std::pair<double, int>> heap_;
  // per-net tree: tv[n][i] vertex, tp[n][i] its parent (-1 for the driver); parents precede
  // children
  std::vector<std::vector<int>> tv, tp;
  std::vector<long long> delay;
  long long total_ = 0;
  // parameters and counters
  double pf0_, pf_mult_, hist_fac_, esc1_, esc2_;
  int lns_, lns_k_, lns_order_;
  double sa_t0_, sa_t1_;
  int gneg_, lns_win_, gneg_sel_;
  double fan_alpha_;
  int lns_mix_, lns_wr_;
  double lns_gamma_;
  int tree_seq_, tie_share_, tie_mid_;
  double ta_t0_;
  long long kick_after_;
  int kick_k_, kick_wr_;
  long long restore_after_;
  int astar_;
  double par_sync_;
  int minld_ = 1;
  std::vector<char> fast_;  // per layer: is a cheapest layer
  // tree / reverse-search scratch for ideas 1 and 2
  std::vector<uint32_t> inT_, sinkm_, rseen_, rdone_;
  std::vector<int> rcost_, rnext_;
  uint32_t tstamp_ = 0, sstamp_ = 0, rstamp_ = 0;
  std::vector<std::pair<int, int>> rheap_;
  std::vector<std::vector<int>> abuckets_;
  std::vector<double> netw_;
  std::vector<char> gaff_;
  int wx0_ = 0, wx1_ = 1 << 30, wy0_ = 0, wy1_ = 1 << 30;  // search window (inclusive)
  double gneg_pf0_, gneg_mult_, gneg_hist_;
  std::vector<int> touched_;
  long long lns_accepted_ = 0;
  // LNS state, kept across lns_run calls
  std::vector<uint32_t> net_mark_;
  uint32_t epoch_ = 0;
  std::vector<int> group_, cand_;
  std::vector<std::vector<int>> old_v_, old_p_;
  std::vector<long long> old_d_;
  std::vector<double> cum_;
  bool track_best_ = false;
  long long best_total_ = 0;
  std::vector<std::vector<int>> best_v_, best_p_;
  std::vector<long long> best_d_;
  Clock::time_point lns_start_{};
  double lns_span_ = 1.0, temp_ = 0.0, thr_ = 0.0;
  double hw_[2] = {1e-2, 1e-2};
  long long hcount_[2] = {0, 0};
  long long since_imp_ = 0, since_best_ = 0;
  // congestion-free tree per net (only other nets' pins blocked) and its delay
  std::vector<std::vector<int>> ideal_v;
  std::vector<long long> ideal_d;
  long long max_moves_;
  int verbose_;
  std::string snap_dir_;
  double snap_s_;
  int snap_neg_;
  int snap_count_ = 0;
  Clock::time_point last_snap_{};

  void snapshot(const char* phase, long long overused) {
    if (snap_dir_.empty()) return;
    char name[64];
    std::snprintf(name, sizeof name, "snap_%04d.sol.json", snap_count_);
    write(snap_dir_ + "/" + name);
    long long self_delay = 0;
    for (int n = 0; n < nn; ++n) self_delay += delay[n];
    std::ofstream idx(snap_dir_ + "/index.jsonl", std::ios::app);
    idx << "{\"i\": " << snap_count_ << ", \"file\": \"" << name << "\", \"t\": "
        << std::chrono::duration<double>(Clock::now() - start_).count() << ", \"phase\": \"" << phase
        << "\", \"self_delay\": " << self_delay << ", \"overused\": " << overused << ", \"moves\": " << moves_
        << "}\n";
    ++snap_count_;
    last_snap_ = Clock::now();
  }

 public:
  void final_snapshot() { snapshot("final", 0); }

 private:
  long long moves_ = 0;
  int sweeps_ = 0;
  int neg_iters_ = 0;

  template <class F>
  inline void for_nb(int v, F&& f) const {
    int x = X[v], y = Y[v], z = Z[v];
    int c = in_.ld[z];
    if (x + 1 < W) f(v + 1, c);
    if (x > 0) f(v - 1, c);
    if (y + 1 < H) f(v + W, c);
    if (y > 0) f(v - W, c);
    if (z + 1 < L) f(v + WH, via);
    if (z > 0) f(v - WH, via);
  }
  inline int edge_w(int u, int v) const { return Z[u] != Z[v] ? via : in_.ld[Z[v]]; }

  void add_occ(int n) { for (int v : tv[n]) ++occ[v]; }
  void sub_occ(int n) { for (int v : tv[n]) --occ[v]; }
  void rip(int n) {
    for (int v : tv[n])
      if (pin_net[v] < 0) owner[v] = -1;
  }
  void place(int n) { for (int v : tv[n]) owner[v] = n; }

  // Build net n's tree from pred[] of the last search (stamp_), computing true delays.
  void build_tree(int n) { delay[n] = build_tree_into(n, tv[n], tp[n]); }
  long long build_tree_into(int n, std::vector<int>& V, std::vector<int>& P) {
    V.clear(); P.clear();
    int d = in_.drv[n];
    V.push_back(d); P.push_back(-1);
    intree[d] = stamp_;
    dly[d] = 0;
    static thread_local std::vector<int> path;
    long long sum = 0;
    for (int s : in_.sinks[n]) {
      path.clear();
      int v = s;
      while (intree[v] != stamp_) { path.push_back(v); v = pred[v]; }
      for (size_t i = path.size(); i-- > 0;) {
        int u = path[i];
        int p = pred[u];
        intree[u] = stamp_;
        dly[u] = dly[p] + edge_w(p, u);
        V.push_back(u); P.push_back(p);
      }
      sum += dly[s];
    }
    return sum;
  }

  // Exact shortest-path tree for net n over vertices free or owned by n (bucket queue).
  template <bool FreeOnly = false>
  bool route_exact(int n) {
    if (!FreeOnly && astar_ && in_.sinks[n].size() == 1) return route_exact_astar(n);
    ++stamp_;
    int remaining = 0;
    for (int s : in_.sinks[n])
      if (target[s] != stamp_) { target[s] = stamp_; ++remaining; }
    int d = in_.drv[n];
    const int B = maxc + 1;
    dist[d] = 0; seen[d] = stamp_; pred[d] = -1;
    buckets[0].push_back(d);
    int queued = 1;
    for (int cur = 0; queued > 0 && remaining > 0; ++cur) {
      auto& b = buckets[cur % B];
      for (size_t i = 0; i < b.size() && remaining > 0; ++i) {
        int v = b[i];
        --queued;
        if (done[v] == stamp_ || dist[v] != cur) continue;
        done[v] = stamp_;
        if (target[v] == stamp_ && --remaining == 0) break;
        for_nb(v, [&](int u, int c) {
          int o = FreeOnly ? pin_net[u] : owner[u];
          if (o >= 0 && o != n) return;
          if (X[u] < wx0_ || X[u] > wx1_ || Y[u] < wy0_ || Y[u] > wy1_) return;
          int nd = cur + c;
          if (seen[u] != stamp_ || nd < dist[u]) {
            seen[u] = stamp_;
            dist[u] = nd;
            pred[u] = v;
            buckets[nd % B].push_back(u);
            ++queued;
          }
        });
      }
      b.clear();
    }
    for (auto& b : buckets) b.clear();
    if (remaining > 0) return false;
    if (!FreeOnly) {
      if (tie_share_) delay[n] = build_tree_share(n);
      else build_tree(n);
    }
    return true;
  }

  // Idea 4: A* for a single-sink net on true delays (bucket queue keyed by delay + bound).
  // The bound (cheapest step delay x Manhattan distance + via delay x layer gap) never
  // overestimates and changes by at most one step's cost, so the first pop of the sink is exact.
  bool route_exact_astar(int n) {
    ++stamp_;
    const int s = in_.sinks[n][0], d = in_.drv[n];
    const int sx = X[s], sy = Y[s], sz = Z[s];
    auto h = [&](int v) { return minld_ * (std::abs(X[v] - sx) + std::abs(Y[v] - sy)) + via * std::abs(Z[v] - sz); };
    const int B = static_cast<int>(abuckets_.size());
    dist[d] = 0; seen[d] = stamp_; pred[d] = -1;
    int f0 = h(d);
    abuckets_[f0 % B].push_back(d);
    int queued = 1;
    bool found = false;
    for (int cur = f0; queued > 0 && !found; ++cur) {
      auto& b = abuckets_[cur % B];
      for (size_t i = 0; i < b.size(); ++i) {
        int v = b[i];
        --queued;
        if (done[v] == stamp_ || dist[v] + h(v) != cur) continue;
        done[v] = stamp_;
        if (v == s) { found = true; break; }
        for_nb(v, [&](int u, int c) {
          int o = owner[u];
          if (o >= 0 && o != n) return;
          if (X[u] < wx0_ || X[u] > wx1_ || Y[u] < wy0_ || Y[u] > wy1_) return;
          int nd = dist[v] + c;
          if (seen[u] != stamp_ || nd < dist[u]) {
            seen[u] = stamp_;
            dist[u] = nd;
            pred[u] = v;
            abuckets_[(nd + h(u)) % B].push_back(u);
            ++queued;
          }
        });
      }
      if (!found) b.clear();
    }
    for (auto& b : abuckets_) b.clear();
    if (!found) return false;
    build_tree(n);
    return true;
  }

  // Idea 2: tree from the last exact search using only tight edges (every sink keeps its
  // shortest delay). Sinks attach farthest first; each walks back through the shortest-path
  // graph to the nearest point already in the tree, adding as few new points as possible.
  long long build_tree_share(int n) {
    auto& V = tv[n];
    auto& P = tp[n];
    V.clear(); P.clear();
    const uint32_t ts = ++tstamp_;
    int d = in_.drv[n];
    V.push_back(d); P.push_back(-1);
    inT_[d] = ts; dly[d] = 0;
    static thread_local std::vector<int> order;
    order.assign(in_.sinks[n].begin(), in_.sinks[n].end());
    std::stable_sort(order.begin(), order.end(), [&](int a, int b) { return dist[a] > dist[b]; });
    auto cmp = [](const std::pair<int, int>& a, const std::pair<int, int>& b) { return a.first > b.first; };
    for (int s : order) {
      if (inT_[s] == ts) continue;
      const uint32_t rs = ++rstamp_;
      rheap_.clear();
      rcost_[s] = 0; rseen_[s] = rs; rnext_[s] = -1;
      rheap_.push_back({0, s});
      int hit = -1;
      while (!rheap_.empty()) {
        std::pop_heap(rheap_.begin(), rheap_.end(), cmp);
        auto [cv, v] = rheap_.back();
        rheap_.pop_back();
        if (rdone_[v] == rs || cv > rcost_[v]) continue;
        rdone_[v] = rs;
        if (inT_[v] == ts) { hit = v; break; }
        for_nb(v, [&](int u, int c) {
          if (done[u] != stamp_ || dist[u] + c != dist[v]) return;
          int nc = cv + (inT_[u] == ts ? 0 : 1 + (fast_[Z[u]] ? tie_mid_ : 0));
          if (rseen_[u] != rs || nc < rcost_[u]) {
            rseen_[u] = rs; rcost_[u] = nc; rnext_[u] = v;
            rheap_.push_back({nc, u});
            std::push_heap(rheap_.begin(), rheap_.end(), cmp);
          }
        });
      }
      if (hit < 0) { std::cerr << "internal error: tie_share found no tight path\n"; std::exit(3); }
      for (int p = hit, v = rnext_[hit]; v != -1; p = v, v = rnext_[v]) {
        inT_[v] = ts;
        dly[v] = dly[p] + edge_w(p, v);
        V.push_back(v); P.push_back(p);
      }
    }
    long long sum = 0;
    for (int s : in_.sinks[n]) sum += dly[s];
    return sum;
  }

  // Negotiated-cost shortest-path tree for net n: other nets' pins are forbidden; a step
  // into v costs (delay + hist[v]) * (1 + pf * occ[v]).
  template <bool Group = false>
  bool route_neg(int n, double pf) {
    if ((tree_seq_ == 1 || (tree_seq_ == 2 && !Group)) && in_.sinks[n].size() > 1) return route_neg_seq<Group>(n, pf);
    if (astar_ && in_.sinks[n].size() == 1) return route_neg_astar<Group>(n, pf);
    ++stamp_;
    int remaining = 0;
    for (int s : in_.sinks[n])
      if (target[s] != stamp_) { target[s] = stamp_; ++remaining; }
    int d = in_.drv[n];
    auto cmp = [](const std::pair<double, int>& a, const std::pair<double, int>& b) { return a.first > b.first; };
    const double w = netw_[n];
    const double wpf = w * pf;
    heap_.clear();
    fdist[d] = 0; seen[d] = stamp_; pred[d] = -1;
    heap_.push_back({0.0, d});
    while (!heap_.empty() && remaining > 0) {
      std::pop_heap(heap_.begin(), heap_.end(), cmp);
      auto [dv, v] = heap_.back();
      heap_.pop_back();
      if (done[v] == stamp_ || dv > fdist[v]) continue;
      done[v] = stamp_;
      if (target[v] == stamp_ && --remaining == 0) break;
      for_nb(v, [&](int u, int c) {
        int pn = Group ? owner[u] : pin_net[u];
        if (pn >= 0 && pn != n) return;
        if (X[u] < wx0_ || X[u] > wx1_ || Y[u] < wy0_ || Y[u] > wy1_) return;
        double nd = fan_alpha_ == 0.0 ? dv + (c + hist[u]) * (1.0 + pf * occ[u])
                                      : dv + (c + w * hist[u]) * (1.0 + wpf * occ[u]);
        if (seen[u] != stamp_ || nd < fdist[u]) {
          seen[u] = stamp_;
          fdist[u] = nd;
          pred[u] = v;
          heap_.push_back({nd, u});
          std::push_heap(heap_.begin(), heap_.end(), cmp);
        }
      });
    }
    if (remaining > 0) return false;
    build_tree(n);
    return true;
  }

  inline double neg_cost(int u, int c, double pf, double w, double wpf) const {
    return fan_alpha_ == 0.0 ? (c + hist[u]) * (1.0 + pf * occ[u]) : (c + w * hist[u]) * (1.0 + wpf * occ[u]);
  }

  // Idea 1: grow the negotiated tree one sink at a time. Each search starts from every point
  // already in the tree at its true delay from the driver (no congestion charged again) and
  // stops at the cheapest remaining sink, whose path is then added.
  template <bool Group>
  bool route_neg_seq(int n, double pf) {
    auto& V = tv[n];
    auto& P = tp[n];
    V.clear(); P.clear();
    const uint32_t ts = ++tstamp_, ss = ++sstamp_;
    int d = in_.drv[n];
    V.push_back(d); P.push_back(-1);
    inT_[d] = ts; dly[d] = 0;
    int remaining = 0;
    for (int s : in_.sinks[n])
      if (sinkm_[s] != ss) { sinkm_[s] = ss; ++remaining; }
    const double w = netw_[n], wpf = w * pf;
    auto cmp = [](const std::pair<double, int>& a, const std::pair<double, int>& b) { return a.first > b.first; };
    static thread_local std::vector<int> path;
    while (remaining > 0) {
      ++stamp_;
      heap_.clear();
      for (int v : V) {
        fdist[v] = dly[v]; seen[v] = stamp_; pred[v] = -1;
        heap_.push_back({static_cast<double>(dly[v]), v});
      }
      std::make_heap(heap_.begin(), heap_.end(), cmp);
      int found = -1;
      while (!heap_.empty()) {
        std::pop_heap(heap_.begin(), heap_.end(), cmp);
        auto [dv, v] = heap_.back();
        heap_.pop_back();
        if (done[v] == stamp_ || dv > fdist[v]) continue;
        done[v] = stamp_;
        if (sinkm_[v] == ss && inT_[v] != ts) { found = v; break; }
        for_nb(v, [&](int u, int c) {
          if (inT_[u] == ts) return;
          int pn = Group ? owner[u] : pin_net[u];
          if (pn >= 0 && pn != n) return;
          if (X[u] < wx0_ || X[u] > wx1_ || Y[u] < wy0_ || Y[u] > wy1_) return;
          double nd = dv + neg_cost(u, c, pf, w, wpf);
          if (seen[u] != stamp_ || nd < fdist[u]) {
            seen[u] = stamp_; fdist[u] = nd; pred[u] = v;
            heap_.push_back({nd, u});
            std::push_heap(heap_.begin(), heap_.end(), cmp);
          }
        });
      }
      if (found < 0) return false;
      path.clear();
      for (int v = found; inT_[v] != ts; v = pred[v]) path.push_back(v);
      for (size_t i = path.size(); i-- > 0;) {
        int u = path[i], p = pred[u];
        inT_[u] = ts;
        dly[u] = dly[p] + edge_w(p, u);
        V.push_back(u); P.push_back(p);
        if (sinkm_[u] == ss) --remaining;
      }
    }
    long long sum = 0;
    for (int s : in_.sinks[n]) sum += dly[s];
    delay[n] = sum;
    return true;
  }

  // Idea 4: negotiated search for a single-sink net with the same admissible bound as A*.
  template <bool Group>
  bool route_neg_astar(int n, double pf) {
    ++stamp_;
    const int s = in_.sinks[n][0], d = in_.drv[n];
    const int sx = X[s], sy = Y[s], sz = Z[s];
    auto h = [&](int v) {
      return static_cast<double>(minld_ * (std::abs(X[v] - sx) + std::abs(Y[v] - sy)) + via * std::abs(Z[v] - sz));
    };
    const double w = netw_[n], wpf = w * pf;
    auto cmp = [](const std::pair<double, int>& a, const std::pair<double, int>& b) { return a.first > b.first; };
    heap_.clear();
    fdist[d] = 0; seen[d] = stamp_; pred[d] = -1;
    heap_.push_back({h(d), d});
    bool found = false;
    while (!heap_.empty()) {
      std::pop_heap(heap_.begin(), heap_.end(), cmp);
      auto [fv, v] = heap_.back();
      heap_.pop_back();
      if (done[v] == stamp_ || fv > fdist[v] + h(v) + 1e-9) continue;
      done[v] = stamp_;
      if (v == s) { found = true; break; }
      double dv = fdist[v];
      for_nb(v, [&](int u, int c) {
        int pn = Group ? owner[u] : pin_net[u];
        if (pn >= 0 && pn != n) return;
        if (X[u] < wx0_ || X[u] > wx1_ || Y[u] < wy0_ || Y[u] > wy1_) return;
        double nd = dv + neg_cost(u, c, pf, w, wpf);
        if (seen[u] != stamp_ || nd < fdist[u]) {
          seen[u] = stamp_; fdist[u] = nd; pred[u] = v;
          heap_.push_back({nd + h(u), u});
          std::push_heap(heap_.begin(), heap_.end(), cmp);
        }
      });
    }
    if (!found) return false;
    build_tree(n);
    return true;
  }
};

// --------------------------------------------------------------------------------------
// Idea 5: T workers run LNS from the same solution with different seeds; every par_sync
// seconds each ends on its best solution and all adopt the overall best.
static void parallel_lns(Router& r, int T, uint64_t seed) {
  r.lns_setup();
  std::vector<std::unique_ptr<Router>> extra;
  std::vector<Router*> all{&r};
  for (int t = 1; t < T; ++t) {
    extra.push_back(std::make_unique<Router>(r));
    extra.back()->reseed(seed * 1000003ULL + static_cast<uint64_t>(t));
    extra.back()->quiet();
    all.push_back(extra.back().get());
  }
  std::vector<long long> base_moves;
  for (auto* x : all) base_moves.push_back(x->moves());
  while (Clock::now() < r.deadline()) {
    auto until = std::min(r.deadline(),
                          Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(r.par_sync())));
    std::vector<char> more(all.size(), 1);
    std::vector<std::thread> th;
    for (size_t i = 0; i < all.size(); ++i)
      th.emplace_back([&, i] { more[i] = all[i]->lns_run(until); all[i]->epoch_end(); });
    for (auto& t : th) t.join();
    Router* best = all[0];
    for (auto* x : all)
      if (x->total() < best->total()) best = x;
    for (auto* x : all)
      if (x != best) x->adopt(*best);
    bool any = false;
    for (char m : more) any = any || m;
    if (!any) break;
  }
  long long extra_moves = 0;
  for (size_t i = 1; i < all.size(); ++i) extra_moves += all[i]->moves() - base_moves[i];
  r.add_moves(extra_moves);
  r.lns_finish();
}

int main(int argc, char** argv) {
  auto t0 = Clock::now();
  std::string inst_path, out_path;
  double time_limit = 30;
  uint64_t seed = 1;
  int threads = 1;
  Options opt;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) { std::cerr << "missing value for " << a << "\n"; std::exit(2); }
      return argv[++i];
    };
    if (a == "--instance") inst_path = next();
    else if (a == "--out") out_path = next();
    else if (a == "--time-limit") time_limit = std::stod(next());
    else if (a == "--seed") seed = std::stoull(next());
    else if (a == "--threads") threads = std::stoi(next());
    else if (a == "--set") {
      std::string kv = next();
      auto eq = kv.find('=');
      if (eq == std::string::npos) { std::cerr << "bad --set " << kv << "\n"; return 2; }
      opt.kv[kv.substr(0, eq)] = kv.substr(eq + 1);
    } else if (a.empty()) {
      continue;
    } else {
      std::cerr << "unknown argument " << a << "\n";
      return 2;
    }
  }
  if (inst_path.empty() || out_path.empty()) {
    std::cerr << "usage: m3d_route --instance X.json --out Y.sol.json --time-limit S --seed N --threads T "
                 "[--set k=v ...]\n";
    return 2;
  }

  // Finish with a safety margin so the file is written before the limit.
  double margin = std::min(1.0, 0.03 * time_limit + 0.05);
  auto deadline = t0 + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(time_limit - margin));

  Instance in = load_instance(inst_path);
  Router r(in, opt, seed, t0, deadline);
  opt.check_unused();

  bool legal = r.negotiate();
  if (!legal) {
    std::cerr << "no legal solution found before the deadline\n";
    std::cout << "{\"legal\": false}\n";
    return 1;
  }
  auto t_legal = Clock::now();
  r.refine();
  if (threads > 1 && r.lns_enabled()) parallel_lns(r, threads, seed);
  else r.lns();
  r.final_snapshot();
  r.write(out_path);
  double secs = std::chrono::duration<double>(Clock::now() - t0).count();
  double ref_secs = std::chrono::duration<double>(Clock::now() - t_legal).count();
  std::printf(
      "{\"legal\": true, \"delay\": %lld, \"iterations\": %d, \"moves\": %lld, \"moves_per_s\": %.1f, "
      "\"legal_s\": %.3f, \"secs\": %.3f}\n",
      r.total(), r.neg_iters(), r.moves(), ref_secs > 0 ? r.moves() / ref_secs : 0.0,
      std::chrono::duration<double>(t_legal - t0).count(), secs);
  return 0;
}
