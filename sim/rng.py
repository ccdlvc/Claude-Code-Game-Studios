"""PCG32 (XSH-RR). Chỉ dùng số nguyên 64/32-bit nên port sang GDScript/C++ cho kết quả y hệt."""
MASK64 = (1 << 64) - 1
MULT = 6364136223846793005


class PCG32:
    def __init__(self, seed: int, seq: int = 54):
        self.state = 0
        self.inc = ((seq << 1) | 1) & MASK64
        self.next_u32()
        self.state = (self.state + seed) & MASK64
        self.next_u32()

    def next_u32(self) -> int:
        old = self.state
        self.state = (old * MULT + self.inc) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & 0xFFFFFFFF
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & 0xFFFFFFFF

    def random(self) -> float:
        """[0,1) với độ phân giải 2^-32."""
        return self.next_u32() / 4294967296.0

    def randint(self, a: int, b: int) -> int:
        """Số nguyên trong [a,b], không dùng modulo (không lệch)."""
        n = b - a + 1
        return a + ((self.next_u32() * n) >> 32)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def chance(self, p: float) -> bool:
        return self.random() < p

    def fork(self, tag: int) -> "PCG32":
        """Nhánh RNG độc lập, xác định theo (state, tag)."""
        return PCG32(self.next_u32() ^ (tag * 2654435761 & 0xFFFFFFFF), seq=tag + 1)
