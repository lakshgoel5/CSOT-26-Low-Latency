class Arena {
    std::vector<std::byte> buf;
    size_t offset = 0;
    
public:
    explicit Arena(size_t cap) : buf(cap) {}

    template <typename T, typename... Args>
    T* alloc(Args&&... args) {
        // round up to alignof(T)
        size_t aligned = (offset + alignof(T) - 1) & ~(alignof(T) - 1);
        if (aligned + sizeof(T) > buf.size()) throw std::bad_alloc{};
        T* p = new (buf.data() + aligned) T(std::forward<Args>(args)...);
        offset = aligned + sizeof(T);
        return p;
    }

    void reset() { offset = 0; }   // "free" everything at once, O(1)
};
