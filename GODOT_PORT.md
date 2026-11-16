# Hướng dẫn port Simulation Core sang Godot (GDScript)

Lõi tham chiếu nằm ở `sim/` (Python, đã có test). Bản Godot phải cho **cùng kết quả** với cùng seed và cùng dữ liệu.
Máy dev hiện tại không có Godot nên chưa có bản GDScript; thứ tự port dưới đây giúp mỗi bước đều kiểm chứng được.

## Thứ tự port (mỗi bước có test để so khớp)
| Bước | File Python | Việc cần khớp | Cách kiểm tra |
|---|---|---|---|
| 1 | `sim/rng.py` | PCG32 | 6 giá trị đầu seed 42, seq 54 = `0xa15c02b7 0x7b47f409 0xba1d3330 0x83d2f293 0xbfa4784b 0xcbed606e` |
| 2 | `sim/data.py` | Đọc CSV (kể cả ô có dấu ngoặc kép), parse `a=1;b=2` | Đếm dòng từng file khớp `content_validator.py` |
| 3 | `sim/formulas.py` | Công thức thuần | Các test trong `tests/test_core.py::TestFormulas` |
| 4 | `sim/model.py` | Chỉ số, level up, mua đồ | `TestMember` |
| 5 | `sim/hunt.py` | `fight`, `run_trip`, `run_hunt` | Cùng seed → cùng `kills/level/gold` (xuất JSON từ Python làm golden file) |
| 6 | `sim/offline.py` | `estimate_rates`, `fast_forward` | Sai lệch XP < 20% so với chạy chính xác |
| 7 | `sim/raid.py` | `form_parties`, `simulate_raid` | Cùng seed → cùng `win/time/deaths` |

## Quy tắc để kết quả giống hệt giữa Python và GDScript
1. **RNG**: chỉ dùng PCG32 của dự án; KHÔNG dùng `randf()/randi()` của Godot trong lõi. GDScript có số nguyên 64-bit có dấu:
   nhân/cộng sẽ tràn đúng kiểu modulo 2^64 như `& MASK64` trong Python, nhưng phải tự cẩn thận khi dịch phải (`>>`)
   (dùng dịch phải logic: `(x >> n) & ((1 << (64 - n)) - 1)`). Kiểm tra bằng 6 giá trị chuẩn ở trên.
2. **Thứ tự rút số ngẫu nhiên** phải giữ nguyên (ví dụ trong `fight`: offset đầu trận của từng thành viên theo thứ tự `party`,
   rồi offset của quái; mỗi đòn thành viên rút 1 số cho dao động sát thương; mỗi đòn quái rút số chọn mục tiêu rồi mới tới dao động).
3. **Số thực**: dùng `float` 64-bit (GDScript `float` là 64-bit). Tránh đổi thứ tự cộng/nhân. `L ** 1.25` dùng `pow()`.
   Với tiền/vật phẩm kết quả cuối nên làm tròn ở mức hiển thị, không làm tròn giữa chừng.
4. **Chọn phần tử nhỏ nhất** (`min(..., key=...)`): khi hai phần tử bằng nhau, Python chọn phần tử **đầu tiên**; giữ quy tắc này.
5. **Hướng sự kiện**: lõi không quét từng tick; thời gian nhảy tới sự kiện kế tiếp. `tick_rate` chỉ để hiển thị/animation.

## Hiệu năng (số đo thật trên máy dev, Python; chưa đo GDScript/điện thoại)
- Đội 5 người, 24 giờ giả lập: chạy chính xác `run_hunt` ≈ 1,6 giây; `fast_forward` mặc định (chunk 2 giờ, 4 chuyến mẫu) ≈ 0,5 giây,
  lệch XP ≈ 1% (đo ở level 10 / 40 / 80, 3 seed). Cấu hình dày (30 phút, 8 mẫu) ≈ 3–4 giây, **chậm hơn** chạy chính xác nên đừng dùng.
- GDScript thường chậm hơn Python vài lần, nên offline dùng `fast_forward`, KHÔNG chạy `run_hunt` đủ độ dài. Cần đo lại bằng thiết bị thật
  (GDD mục 12.1); nếu chậm: giảm số mẫu, tăng chunk (14400 giây vẫn lệch ≤ 4%), hoặc chuyển phần nóng sang GDExtension.
- Raid cả bang hàng chục người: `simulate_raid` hướng sự kiện (vài nghìn sự kiện); phần vẽ phải giới hạn sprite (GDD 6.13).

## Việc chưa có trong lõi (cố ý để sau)
Skill thật (hiện gộp vào hệ số `skill_dps_bonus`), thuốc/đồ ăn, trait, party tự ghép theo điểm, tuyển mộ, rời bang/đàm phán,
chuyển sinh/Phi Thăng, công trình, nhiệm vụ, bang NPC/Lôi Đài, lưu/tải. Mỗi mục có dữ liệu CSV tương ứng; thêm vào lõi theo thứ tự GDD (mục 12.2).

## Bổ sung v1.0
- `formulas.xp_need(L, cfg, rebirth)` có hệ số đầu game nhanh + chuyển sinh chậm dần (`xp_early_*`, `xp_rebirth_mult_n`).
- `sim/economy.py` (giải tích): thu nhập tham chiếu, tiêu hao, chi phí cường hoá kỳ vọng. Port sang GDScript cùng công thức; test Markov dùng RNG tất định.
