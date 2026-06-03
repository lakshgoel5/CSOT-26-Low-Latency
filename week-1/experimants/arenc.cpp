#include <cstddef>
#include <new>
#include <utility>
#include <vector>

class Arena {
    std::vector<unsigned char> buf;
    size_t offset = 0;
    
public:
    // Explicit: Prevents implicit conversions from size_t to Arena
    explicit Arena(size_t cap) : buf(cap) {}

    template <typename T, typename... Args>
    // typename... Args: Variadic templates - allows the function to accept any number of arguments
    // Args&&... args: Forwarding references - allows the function to accept arguments by reference or rvalue reference
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
