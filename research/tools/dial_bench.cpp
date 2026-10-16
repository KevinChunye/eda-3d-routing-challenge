// Inner-loop speed check: full single-source shortest-path search on an M3D grid
// using flat arrays and a bucket queue (Dial's algorithm; edge costs are small ints).
// Usage: dial_bench W H L  -> prints microseconds per search.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

int main(int argc, char** argv) {
    const int W = std::atoi(argv[1]), H = std::atoi(argv[2]), L = std::atoi(argv[3]);
    const int ld[6] = {6, 4, 2, 2, 4, 6};
    const int via = 3, maxc = 6;
    const int n = W * H * L;
    std::vector<int32_t> dist(n);
    std::vector<std::vector<int32_t>> buckets(maxc + 1);
    const int reps = 200;
    long long checksum = 0;
    auto t0 = std::chrono::steady_clock::now();
    for (int r = 0; r < reps; ++r) {
        const int src = (r * 7919) % (W * H);  // a vertex on layer 0
        std::fill(dist.begin(), dist.end(), INT32_MAX);
        for (auto& b : buckets) b.clear();
        dist[src] = 0;
        buckets[0].push_back(src);
        int cur = 0, pending = 1;
        while (pending > 0) {
            auto& b = buckets[cur % (maxc + 1)];
            while (!b.empty()) {
                int u = b.back(); b.pop_back(); --pending;
                if (dist[u] != cur) continue;
                int z = u / (W * H), rem = u % (W * H), y = rem / W, x = rem % W;
                auto relax = [&](int v, int c) {
                    int nd = cur + c;
                    if (nd < dist[v]) { dist[v] = nd; buckets[nd % (maxc + 1)].push_back(v); ++pending; }
                };
                if (x > 0) relax(u - 1, ld[z]);
                if (x < W - 1) relax(u + 1, ld[z]);
                if (y > 0) relax(u - W, ld[z]);
                if (y < H - 1) relax(u + W, ld[z]);
                if (z > 0) relax(u - W * H, via);
                if (z < L - 1) relax(u + W * H, via);
            }
            ++cur;
        }
        checksum += dist[n - 1];
    }
    double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / reps;
    std::printf("{\"grid\": \"%dx%dx%d\", \"vertices\": %d, \"cpp_us_per_search\": %.1f, \"checksum\": %lld}\n",
                W, H, L, n, us, checksum);
}
