"""Offline progress theo kiểu 'ước lượng bằng mẫu': mô phỏng vài chuyến trên bản sao, lấy tốc độ trung bình,
áp dụng cho một đoạn thời gian, rồi lặp lại (vì level đổi làm tốc độ đổi). Không cần quét từng tick."""
import copy
from .hunt import run_trip
from .model import auto_gear


def estimate_rates(party, ground_id, data, rng, trips=8):
    clone = copy.deepcopy(party)
    base = {m.id: (m.xp_total, m.gold_total, m.kills, m.deaths) for m in clone}
    total_t = 0.0
    for _ in range(trips):
        total_t += run_trip(clone, ground_id, data, rng).time_s
    rates = {}
    for m in clone:
        x0, g0, k0, d0 = base[m.id]
        rates[m.id] = ((m.xp_total - x0) / total_t, (m.gold_total - g0) / total_t,
                       (m.kills - k0) / total_t, (m.deaths - d0) / total_t)
    return rates


def fast_forward(party, ground_id, seconds, data, rng, chunk_s=7200.0, trips=4):
    """Mặc định (2 giờ, 4 chuyến mẫu): đo được lệch ~1% XP so với chạy chính xác và nhanh hơn vài lần.
    Cấu hình dày hơn (30 phút, 8 mẫu) chậm hơn cả chạy chính xác, không có lợi."""
    done = 0.0
    carry_d = {m.id: 0.0 for m in party}
    while done < seconds:
        dt = min(chunk_s, seconds - done)
        rates = estimate_rates(party, ground_id, data, rng, trips)
        for m in party:
            rx, rg, rk, rd = rates[m.id]
            m.gain_xp(rx * dt, data)
            m.gold += rg * dt
            m.gold_total += rg * dt
            m.kills += int(rk * dt)
            carry_d[m.id] += rd * dt
            m.deaths += int(carry_d[m.id])
            carry_d[m.id] -= int(carry_d[m.id])
            auto_gear(m, data)
        done += dt
    return done
