// Exercise the production witness-to-selector conversion without running a SAT benchmark.
#include "closure_bridge.cpp"

int main() {
    unsigned original, count;
    while (std::cin >> original >> count) {
        if (original > 65535 || count < 2 || count > 40) return 1;
        std::vector<Step> path;
        for (unsigned i = 0; i < count; ++i) {
            unsigned a, b, x;
            if (!(std::cin >> a >> b >> x) || (a | b | x) > 65535) return 1;
            path.push_back({Signal(a), Signal(b), Signal(x)});
        }
        Signal image = normalized(original);
        for (Signal target : images(image)) {
            int selectors[40][3];
            if (!restore_gates(path, image, target, selectors)) return 2;
            std::cout << original << ' ' << target;
            for (unsigned i = 0; i < count; ++i) {
                for (int v : selectors[i]) std::cout << ' ' << v;
            }
            std::cout << '\n';
        }
    }
    return !std::cin.eof();
}
