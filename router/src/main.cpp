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
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <string>
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
    verbose_ = opt.get_int("verbose", 0);

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
    ideal_v.resize(nn);
    ideal_d.assign(nn, 0);
    std::vector<int> tmpP;
    for (int n = 0; n < nn; ++n) {
      route_exact<true>(n);
      ideal_d[n] = build_tree_into(n, ideal_v[n], tmpP);
    }
    std::fill(occ.begin(), occ.end(), 0);
    std::fill(hist.begin(), hist.end(), 0.0);
    std::vector<uint32_t> net_mark(nn, 0);
    uint32_t epoch = 0;
    std::vector<int> group, cand;
    std::vector<std::vector<int>> old_v(lns_k_), old_p(lns_k_);
    std::vector<long long> old_d(lns_k_);
    std::vector<double> cum(nn);
    // best solution seen (annealing may leave it)
    long long best_total = total_;
    std::vector<std::vector<int>> best_v, best_p;
    std::vector<long long> best_d;
    bool have_best = false;
    if (sa_t0_ > 0) { best_v = tv; best_p = tp; best_d = delay; have_best = true; }
    auto lns_start = Clock::now();
    double lns_span = std::max(1e-3, std::chrono::duration<double>(deadline_ - lns_start).count());
    double temp = sa_t0_;
    std::uniform_real_distribution<double> unif(0.0, 1.0);
    double hw[2] = {1e-2, 1e-2};
    long long hcount[2] = {0, 0};
    while (true) {
      auto now = Clock::now();
      if (now >= deadline_ || (max_moves_ >= 0 && moves_ >= max_moves_)) break;
      if (sa_t0_ > 0 && (moves_ & 63) == 0) {
        double frac = std::chrono::duration<double>(now - lns_start).count() / lns_span;
        temp = sa_t0_ * std::pow(sa_t1_ / sa_t0_, std::min(1.0, frac));
      }
      double acc = 0;
      for (int n = 0; n < nn; ++n) {
        acc += static_cast<double>(delay[n] - ideal_d[n]);
        cum[n] = acc;
      }
      if (acc <= 0) break;
      double r = std::uniform_real_distribution<double>(0.0, acc)(rng_);
      int t = static_cast<int>(std::upper_bound(cum.begin(), cum.end(), r) - cum.begin());
      if (t >= nn) t = nn - 1;
      ++epoch;
      net_mark[t] = epoch;
      cand.clear();
      int heur = 0;
      if (lns_mix_) heur = unif(rng_) * (hw[0] + hw[1]) < hw[0] ? 0 : 1;
      auto move_t0 = Clock::now();
      if (heur == 0) {
        for (int v : ideal_v[t]) {
          int o = owner[v];
          if (o >= 0 && net_mark[o] != epoch) { net_mark[o] = epoch; cand.push_back(o); }
        }
      } else {
        int c = ideal_v[t][std::uniform_int_distribution<size_t>(0, ideal_v[t].size() - 1)(rng_)];
        int cx = X[c], cy = Y[c];
        for (int z = 0; z < L; ++z)
          for (int y = std::max(0, cy - lns_wr_); y <= std::min(H - 1, cy + lns_wr_); ++y)
            for (int x = std::max(0, cx - lns_wr_); x <= std::min(W - 1, cx + lns_wr_); ++x) {
              int o = owner[(z * H + y) * W + x];
              if (o >= 0 && net_mark[o] != epoch) { net_mark[o] = epoch; cand.push_back(o); }
            }
      }
      std::shuffle(cand.begin(), cand.end(), rng_);
      if (static_cast<int>(cand.size()) > lns_k_ - 1) cand.resize(lns_k_ - 1);
      group.clear();
      group.push_back(t);
      group.insert(group.end(), cand.begin(), cand.end());
      if (lns_order_ == 1) std::shuffle(group.begin(), group.end(), rng_);
      long long old_sum = 0;
      for (size_t i = 0; i < group.size(); ++i) {
        int n = group[i];
        old_v[i] = tv[n]; old_p[i] = tp[n]; old_d[i] = delay[n];
        old_sum += delay[n];
        rip(n);
      }
      if (lns_win_ >= 0) {
        wx0_ = W; wx1_ = -1; wy0_ = H; wy1_ = -1;
        for (size_t i = 0; i < group.size(); ++i)
          for (int v : old_v[i]) {
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
      wx0_ = 0; wx1_ = 1 << 30; wy0_ = 0; wy1_ = 1 << 30;
      if (lns_mix_) {
        double us = std::max(1.0, std::chrono::duration<double, std::micro>(Clock::now() - move_t0).count());
        double gain = routed == group.size() && new_sum < old_sum ? static_cast<double>(old_sum - new_sum) : 0.0;
        hw[heur] = std::max(1e-4, (1 - lns_gamma_) * hw[heur] + lns_gamma_ * gain / us);
        ++hcount[heur];
      }
      if (routed == group.size() &&
          (new_sum <= old_sum || (sa_t0_ > 0 && unif(rng_) < std::exp(-(new_sum - old_sum) / temp)))) {
        total_ += new_sum - old_sum;
        ++lns_accepted_;
        if (sa_t0_ > 0 && total_ < best_total) {
          best_total = total_;
          best_v = tv; best_p = tp; best_d = delay;
          have_best = true;
        }
        continue;
      }
      for (size_t i = 0; i < routed; ++i) rip(group[i]);
      for (size_t i = 0; i < group.size(); ++i) {
        int n = group[i];
        tv[n].swap(old_v[i]); tp[n].swap(old_p[i]); delay[n] = old_d[i];
        place(n);
      }
    }
    if (sa_t0_ > 0 && total_ > best_total && have_best) {
      for (int n = 0; n < nn; ++n) rip(n);
      tv = best_v; tp = best_p; delay = best_d;
      for (int n = 0; n < nn; ++n) place(n);
      total_ = best_total;
    }
    if (verbose_)
      std::cerr << "lns moves " << moves_ << " accepted " << lns_accepted_ << " total " << total_ << " heur "
                << hcount[0] << "/" << hcount[1] << " w " << hw[0] << "/" << hw[1] << "\n";
  }

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
  std::vector<double> netw_;
  std::vector<char> gaff_;
  int wx0_ = 0, wx1_ = 1 << 30, wy0_ = 0, wy1_ = 1 << 30;  // search window (inclusive)
  double gneg_pf0_, gneg_mult_, gneg_hist_;
  std::vector<int> touched_;
  long long lns_accepted_ = 0;
  // congestion-free tree per net (only other nets' pins blocked) and its delay
  std::vector<std::vector<int>> ideal_v;
  std::vector<long long> ideal_d;
  long long max_moves_;
  int verbose_;
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
    if (!FreeOnly) build_tree(n);
    return true;
  }

  // Negotiated-cost shortest-path tree for net n: other nets' pins are forbidden; a step
  // into v costs (delay + hist[v]) * (1 + pf * occ[v]).
  template <bool Group = false>
  bool route_neg(int n, double pf) {
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
};

// --------------------------------------------------------------------------------------
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
  (void)threads;  // single-threaded for now

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
  r.lns();
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
