// Export the implementation's finite group actions and partner minima for audit.
#define FRONTIER_LIBRARY
#include "frontier.cpp"

int main(int argc,char** argv) {
    if (argc!=3) return 2;
    Search s(4,0);
    std::ofstream maps(argv[1],std::ios::binary), table(argv[2]);
    if (!maps || !table) return 3;
    for (const auto& map : s.images)
        maps.write(reinterpret_cast<const char*>(map.data()),map.size()*sizeof(Wire));
    for (int f=0; f<s.count; f+=2) if (s.rep[f]==f) {
        std::vector<int> m(s.count,infinity);
        for (int p=2; p<s.count; p+=2)
            m[s.rep[p]]=std::min(m[s.rep[p]],s.partner(p,f));
        for (int p=2; p<s.count; p+=2) if (s.rep[p]==p)
            table<<p<<" "<<f<<" "<<m[p]<<"\n";
    }
    return maps && table ? 0 : 3;
}
