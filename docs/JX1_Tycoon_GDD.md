# JX1 Tycoon (tên tạm, PHẢI đổi trước khi phát hành) — GDD & Technical Spec v1.0

> Nhãn: **[CHỐT]** bạn đã quyết · **[ĐỀ XUẤT]** mình đề xuất, chờ duyệt · **[XÁC NHẬN]** cần bạn xác nhận cách mình hiểu · **[MỞ]** câu hỏi còn lại (mục 15).
> Mọi con số trong tài liệu này là điểm khởi đầu, sẽ chỉnh bằng simulator headless (mục 4.4).

---

## 1. Tổng quan
- Thể loại: Tycoon / Idle / AFK, pixel 2D, mô phỏng realtime trên map.
- Vai trò: Bang chủ quản lý bang hội võ lâm: tuyển thành viên, xây công trình, phân phối vật tư, điều phối đánh boss.
- Cơ chế nền: vòng lặp của Evil Hunter Tycoon (EHT): thành viên đi săn → mang tài nguyên về → bang bán/chế tạo/nâng cấp → thành viên mạnh hơn.
- Chất liệu: võ lâm, ngũ hành, 10 môn phái, chuyển sinh. **Nội dung (tên, skill, item, map, art) làm mới hoàn toàn** [CHỐT].
- **Bối cảnh: lồng ghép lịch sử/văn hoá Việt Nam; bạn tự đặt tên** [CHỐT]. Mọi tên trong tài liệu này (phái, vùng, công trình) chỉ là placeholder; code dùng ID bất biến, tên hiển thị nằm trong i18n (xem phụ lục 16).
- Single-player offline; cloud save đa nền tảng; bảng xếp hạng bang hội + thành viên [CHỐT].
- Ngôn ngữ: Tiếng Việt + Tiếng Anh [CHỐT].

## 2. Quyết định đã chốt

| Mục | Quyết định |
|---|---|
| Nền tảng | Mobile → PC → Web [CHỐT] |
| Phát hành | Thương mại, dev solo [CHỐT] |
| Mô hình tiền | Bản Free (quảng cáo banner dưới, tính năng nâng cao bị khoá) + bản Trả phí (không quảng cáo, mở tính năng nâng cao). Nhiệm vụ ngày/tuần là nơi mở quảng cáo thưởng ở bản Free [CHỐT] |
| Phạm vi | Bản hoàn chỉnh, đủ môn phái, chuyển sinh [CHỐT] |
| Công trình | Thiết kế lại theo bang hội [CHỐT] |
| Chiến đấu | Realtime trên map [CHỐT] |
| CA/PA | 0–200; người chơi chỉ thấy ước lượng; PA chính xác là tính năng thương mại [CHỐT] |
| Rời bang | Có điều kiện ở lại + đàm phán; bình thường chỉ bị thương → dưỡng sức [CHỐT] |
| Đổi phái | Được [CHỐT] |
| Người rời bang | Có thể quay lại theo cốt truyện, hoặc vào danh sách chung để bang khác mời [CHỐT] |
| Tuyển mộ | Chủ động (mời, thám tử) + thụ động [CHỐT] |
| Tiến trình | Chơi vô hạn; có offline progress [CHỐT] |
| AI | Tuỳ chọn; LLM nhỏ + template khung chặt, là tính năng phụ [CHỐT] |
| Hình thức phát hành | 1 app + IAP "Premium" mua một lần [CHỐT] |
| Nhiệm vụ ngày/tuần | Có mục xem quảng cáo thưởng (tuỳ chọn) ở Free; Premium nhận thẳng thưởng [CHỐT] |
| PC (Steam) | Chỉ bản trả phí, không quảng cáo [CHỐT] |
| PvP & chuyển nhượng | Bang NPC mô phỏng cục bộ trước; cloud bất đồng bộ để sau, tuỳ chọn [CHỐT theo đề xuất] |
| Lộ trình ra mắt | Ra mắt theo wave, nhưng plan đầy đủ tất cả ngay từ đầu (mục 12.5) [CHỐT] |
| PA chính xác | Bán riêng, không nằm trong Premium (mục 11.5) [CHỐT] |
| Art | Dùng công cụ AI + chỉnh tay (mục 12.4) [CHỐT] |
| iOS | Có Mac, chưa có Apple Developer → Android trước, iOS sau (mục 12.1) [CHỐT] |
| Đặt tên | Bạn tự đặt, theo lịch sử Việt Nam (phụ lục 16) [CHỐT] |
| Chủ đề | Hướng A + B: vùng theo địa danh/thời kỳ lịch sử, quái/boss theo truyền thuyết dân gian [CHỐT] |
| Boss | Chỉ là quái thú/linh vật; nhân vật lịch sử thật chỉ làm NPC/Trưởng Lão/cốt truyện [CHỐT] |
| Đội hình (party) | Tối đa 5 người/đội; ưu tiên mỗi đội có 1 thành viên buff/hỗ trợ (mục 6.12) [CHỐT] |
| Wave 1 | Xác nhận 5 phái `kim_2, moc_1, thuy_1, hoa_2, tho_1` + 11 vùng + chuyển sinh 1 [CHỐT] |
| Android | Đã có máy thật + tài khoản Google Play Console [CHỐT] |
| Công cụ art | Chỉ dùng công cụ AI miễn phí, **không thuê artist** [CHỐT]; chọn công cụ cụ thể ở spike art (mục 12.4) |
| Raid Boss Hoàng Kim | **Cả bang cùng đánh** (mọi thành viên đủ điều kiện, không giới hạn số party) (mục 6.5, 6.13) [CHỐT] |
| Thiếu buffer ở Wave 1 | Phương án A: giữ 5 phái, tăng tỉ lệ ứng viên `moc_1`, có vật phẩm Lệnh Kỳ [CHỐT] |
| Bán PA chính xác | Bán cả Thiên Cơ Kính và Thiên Nhãn; miễn phí 1 Kính/tuần qua nhiệm vụ [CHỐT] |
| Đặt tên | Mình đề xuất, bạn duyệt/chỉnh: `i18n/names_vi.csv`, `names_en.csv` (mục 17) [CHỐT] |
| Dữ liệu | Đã có đủ cả 3 wave + công cụ kiểm tra (mục 17) |
| Nhịp chơi | Đầu game **nhanh** để tạo hứng; **chậm dần** sau mỗi lần chuyển sinh (mục 4.3) [CHỐT hướng; con số là ĐỀ XUẤT] |
| Tiêu vàng | Thuốc, buff ăn/uống, cường hoá, thuế và phí duy trì bang (mục 19) [CHỐT soạn; con số là ĐỀ XUẤT] |
| Tra cứu điều khoản AI art | Đã tra bước đầu, kết quả ở 12.4.1 (cần đọc điều khoản gốc trước khi dùng) |
| Bước tiếp theo | Ghi lại kế hoạch mở rộng lõi mô phỏng (mục 20) + bộ prompt để tiến hành code (mục 21) [CHỐT] |

## 3. Engine & nền tảng kỹ thuật

### 3.1 Đề xuất engine: **Godot 4.x** (GDScript, C++ GDExtension khi cần)
Lý do theo tiêu chí của bạn (bộ cài nhỏ, hiệu năng, dev solo):
- Bản export mobile nhỏ, 2D pixel là thế mạnh, không phí bản quyền/royalty, một project ra Android/iOS/PC/Web.
- GDScript nhanh để lặp; logic nặng viết thành module C# hoặc GDExtension nếu cần.
- Cloud/leaderboard dùng REST (HTTPRequest) nên không phụ thuộc SDK engine.

Rủi ro (cần kiểm chứng sớm bằng "spike" 1–2 tuần, xem mục 12):
- SDK quảng cáo (AdMob/mediation), IAP, Google/Apple Sign-In trên Godot đi qua plugin Android/iOS (có plugin chính thức/cộng đồng nhưng phải test phiên bản hiện hành với Godot bản bạn dùng).
- Build iOS cần máy Mac + tài khoản Apple Developer.
- Web export nặng, hạn chế thread (phù hợp vì Web là ưu tiên cuối).

**Phương án B: Unity 2D** nếu spike cho thấy ads/IAP/đăng nhập trên Godot tốn công hơn dự kiến (SDK Unity trưởng thành hơn, đổi lại bộ cài và runtime nặng hơn). Quyết định cuối sau spike.

### 3.2 Kiến trúc phân lớp
```
[Presentation]  Godot scenes: map, sprite, UI, VFX, audio, i18n
      ↑ events (read-only)           ↓ commands (người chơi/AI)
[Simulation Core]  Thuần logic, KHÔNG phụ thuộc node/scene, chạy headless
      - Fixed timestep (10 tick/s), RNG có seed, không dùng float lệch giữa máy (ưu tiên số nguyên/fixed-point cho tiền, drop)
[Data Layer]  JSON/CSV → Resource: skill, item, quái, bãi, công trình, trait, nhiệm vụ
[Services]  Save, Cloud, Leaderboard, Ads, IAP, Entitlement(Free/Premium), AI(optional), Analytics
```
Simulation Core dùng chung cho: realtime, offline fast-forward, simulator cân bằng, kiểm tra điểm bảng xếp hạng phía server.

### 3.3 Cấu trúc thư mục dự án [ĐỀ XUẤT]
```
/core        # simulation: member, combat, economy, guild, events (không import scene)
/data        # *.json|csv: schools, skills, items, monsters, zones, buildings, traits, quests
/ui          # màn hình, popup, theme
/world       # map, spawner, view cho member/quái/boss
/services    # save, cloud, ads, iap, entitlement, ai
/i18n        # vi.csv, en.csv (key → text), KHÔNG hard-code chuỗi
/tools       # importer, balance_sim, content_validator
/tests       # unit test cho core (GUT hoặc script riêng)
```

### 3.4 Thứ tự tick của Simulation Core [ĐỀ XUẤT]
1. Nhận commands (người chơi/AI) → validate.
2. Cập nhật trạng thái member theo state machine (mục 6.4).
3. Chiến đấu/AI hành vi trong khung nhìn; thống kê cho vùng ngoài khung (LOD).
4. Xử lý drop, giao dịch, thuế, công trình sản xuất.
5. Xử lý sự kiện theo thời gian (boss hoàng kim mỗi giờ, hợp đồng, nhiệm vụ).
6. Phát events cho Presentation; ghi log cho Giang Hồ Ký.

### 3.5 Hiệu năng mobile
- Mục tiêu 30 FPS máy tầm trung; object pooling (quái, damage number, drop); atlas sprite.
- LOD mô phỏng: bãi đang xem = chi tiết; bãi khác = thống kê theo công thức (dùng chung với offline fast-forward).
- Sprite dạng **paper-doll modular** (thân + vũ khí + trang phục theo phái + palette swap theo hệ) để giảm khối lượng art cho 10 phái (rất quan trọng với dev solo).

## 4. Dữ liệu & công thức nền

### 4.1 Schema chính (rút gọn)
```jsonc
Member: { id, name, school_id|null, element, level, rebirth, ca, pa, traits[], stats{str,agi,vit,int,luck},
  skills[{id,lv,xp}], equipment{}, inventory[], gold, state, ground_id, loyalty, mood, satiety, stamina, hp,
  contract{salary, demands[]}, origin{type:"walk_in|recruited|returned|poached"}, history[] }
Item: { id, slot, school_req|null, element, level_req, rarity, stats, price, tags }
Monster: { id, zone_id, level, element, role, skills[], drop_table }
Ground(bãi): { id, zone_id, level_range, monster_pool, capacity, spawn_rate }
Building: { id, kind, levels[{cost, time, effects}] }
Guild: { level, funds, fame, member_cap, buildings[], storage, market, quests, rivals[] }
Party: { id, leader_id, member_ids[<=5], ground_id, locked(bool), formed_at, comp_score, loot_rule }
```

### 4.2 Công thức khởi điểm [ĐỀ XUẤT — chỉnh bằng simulator]
- Quái: `hp(L) = 40·L^1.3` (đã hiệu chỉnh bằng calibrate.py; 1.6 làm quái quá trâu), `atk(L) = 6·L^1.25`, `def(L) = 3·L^1.2`; boss/elite nhân hệ số.
- XP cần: `xp_need(L) = 100·L^1.7`, nhân thêm hệ số nhịp ở 4.3.
- Ngũ hành: khắc ×1.25 sát thương gây ra, bị khắc ×0.80, cùng hệ ×0.95; tương sinh cho buff nhỏ khi đồng đội khác hệ sinh nhau.
  - Tương khắc: Kim→Mộc→Thổ→Thuỷ→Hoả→Kim. Tương sinh: Kim→Thuỷ→Mộc→Hoả→Thổ→Kim.
- Núm chỉnh nhịp (data/sim_params.csv, config.csv): `xp_kill_coef=1.5`, `monster_dmg_factor=0.05`, `raid_hp_mult=6`, `raid_dmg_mult=1`.
- Tốc độ tăng trưởng: `growth_mult = 0.6 + 0.8·(PA/200)` áp cho XP, luyện skill; tỷ lệ rơi đồ hiếm cũng nhân theo `PA`.

### 4.3 Nhịp chơi: nhanh đầu game, chậm dần theo chuyển sinh [CHỐT hướng]
- Công thức: `xp_need(L, rebirth) = 100·L^1.7 × early(L) × xp_rebirth_mult[rebirth]`, với `early(L) = floor + (1−floor)·min(1, L/end)`; `xp_early_floor=0.08`, `xp_early_end=40`.
- `xp_rebirth_mult` = 1, 3, 5, 8, 12, 18 cho chuyển sinh 0…5 (khoá trong `config.csv`, validator bắt buộc tăng dần).
- Kết quả đo (đội chuẩn 5 người, PA 100, AFK 24/7; số này dài gấp ~2–4 lần với người chơi thật vì offline cap 8/24 giờ): lên lv100 ≈ **71 giờ**; lv100→120 ≈ 69 giờ; →140 ≈ 4,6 ngày; →160 ≈ 8,5 ngày; →180 ≈ 13,3 ngày; →200 ≈ 21,3 ngày; tổng ≈ 54 ngày. Solo `kim_2` lên lv100 ≈ 4,2 ngày (các phái khác 5–7,5 ngày).
- Mốc hứng thú đầu game: lv10 sau ~2–4 giờ AFK (bị chặn bởi thời gian đi lại/chuyến săn, không phải XP). Muốn nhanh hơn nữa dùng **thưởng tân thủ** theo thời gian (ví dụ XP ×3 trong 30 phút đầu), không giảm thêm `early_floor`.
- Bù lại độ chậm: mỗi lần chuyển sinh có phần thưởng (mục 6.10) và mở nội dung mới (vùng, bí kíp, Tháp); đây là chỗ cần thử nghiệm với người chơi thật.
- Ràng buộc: nhịp phải đo lại sau khi tích hợp skill thật, cường hoá, buff ăn/uống (mục 20).

### 4.4 Balance simulator (bắt buộc)
Công cụ `/tools/balance_sim` chạy Simulation Core headless với seed cố định, xuất CSV: vàng/giờ, level/giờ, tỉ lệ boss thắng, lạm phát. Mỗi lần đổi bảng số phải chạy trước khi commit.

## 5. Hệ thống CA / PA / Trait

### 5.1 CA / PA
- `PA` (0–200): trần tiềm năng, ẩn, cố định từ lúc sinh ra. Ảnh hưởng tốc độ XP/skill và drop (4.2), và độ hiếm.
- `CA` (0–200): tính ra, không lưu độc lập.
  ```
  CA_raw = 200 · (0.40·L_norm + 0.25·S_norm + 0.25·E_norm + 0.10·T_norm)
  CA = CA_raw                          nếu CA_raw ≤ PA
  CA = PA + 0.5·(CA_raw − PA)          nếu CA_raw > PA   // trang bị/skill vẫn đẩy vượt nhưng giảm dần
  ```
  (L: level so với cap hiện tại, S: tổng cấp skill, E: điểm trang bị, T: trait.)
- **Hiển thị ước lượng**: sao = `round(PA/20)/2` (0–5, nửa sao). Khoảng giá trị: tâm = PA + nhiễu **cố định theo member_id** (không random lại mỗi lần xem để người chơi không dò ra giá trị bằng cách xem lặp); độ rộng khoảng thu hẹp theo cấp Thám Tử Quán, thời gian ở bang, trait "Tinh Mắt" của bang chủ.
- **PA chính xác** = tính năng thương mại (Premium hoặc vật phẩm, xem mục 11).

### 5.2 Trait ẩn
- 1–3 trait/member, lộ dần theo thời gian ở bang, sự kiện, hoặc Ngộ Đạo Đài. Tương ứng "characterization" (EHT có 33 loại); mục tiêu 40 trait: tính cách (tham, hào sảng, trung thành, nóng nảy…), thiên phú (tốc độ luyện), ngộ tính (xác suất ngộ skill), may mắn (drop), hành vi (mua sắm/đàm phán/xin rời).
- Mỗi trait: `{id, tier, effects[], conflicts[], reveal_condition}`. Danh sách đầy đủ sinh ở bước data (mục 12).

## 6. Gameplay chi tiết

### 6.1 Ngũ hành & 10 môn phái (nội dung mới) [ĐỀ XUẤT]
Mỗi hệ 2 phái, mỗi phái một vai trò rõ trong boss raid. **Tên phái trong bảng chỉ là placeholder** (sẽ thay bằng tên theo lịch sử Việt Nam do bạn đặt, phụ lục 16). ID cố định theo thứ tự bảng: `kim_1, kim_2, moc_1, moc_2, thuy_1, thuy_2, hoa_1, hoa_2, tho_1, tho_2`:

| Hệ | Phái | Vai trò | Vũ khí | Cơ chế đặc trưng |
|---|---|---|---|---|
| Kim | Thiết Huyết Môn | Tank | Đao nặng + giáp | Phản sát thương, khiêu khích |
| Kim | Kim Phong Kiếm Phái | Melee burst | Kiếm | Combo, chí mạng cao |
| Mộc | Thanh Mộc Cốc | Hồi máu/hỗ trợ | Trượng | Hồi HP, giải độc, buff |
| Mộc | Độc Vân Giáo | DoT/Debuff | Ám khí/độc | Độc cộng dồn, giảm phòng |
| Thuỷ | Băng Tâm Viện | Khống chế/Pháp sư | Cầm/Phiến | Làm chậm, đóng băng, AoE |
| Thuỷ | Thuỷ Nguyệt Am | Buff/Hồi nội lực | Kiếm mảnh/Phất trần | Buff đội hình, hồi nội lực |
| Hoả | Liệt Diễm Bang | Melee DPS | Quyền/Côn | Bùng nổ, đốt |
| Hoả | Xích Yên Đường | Ranged DPS | Cung/Phi tiêu lửa | Tầm xa, sát thương theo thời gian |
| Thổ | Hậu Thổ Sơn Trang | Tank/Hộ vệ | Khiên + thương | Giảm sát thương, bảo hộ đồng đội |
| Thổ | Địa Sát Môn | Khống chế/Triệu hồi | Trận bàn/Bẫy | Bẫy, triệu hồi, choáng |

Người không gia nhập phái: cấp 0, học cơ bản, chọn phái khi đạt điều kiện (đề xuất lv10, cho phép đổi phái sau, xem 6.9).

### 6.2 Cây skill (khung)
Mỗi phái **12 skill**: 4 chủ động cơ bản (lv 1–20), 4 nội công/bị động, 2 tuyệt kỹ (mở ở lv 60 và lv 100), 2 bí kíp ẩn (mở sau chuyển sinh, học ở Tàng Kinh Các). Điều kiện: level, skill tiền đề, trait/ngộ tính.
Ví dụ (placeholder):
- Thiết Huyết Môn: *Thiết Bích* (chủ động, tạo khiên, ×1.5 phòng 4s), *Huyết Phản* (bị động, phản 10% sát thương), *Phá Quân Trảm* (tuyệt kỹ lv60), *Kim Cương Bất Hoại* (bí kíp).
- Thanh Mộc Cốc: *Hồi Xuân* (hồi HP đơn), *Mộc Linh Trận* (hồi vùng), *Độc Giải Thảo* (bị động), *Sinh Mệnh Nguyên* (bí kíp hồi sinh 1 lần/trận).
Toàn bộ 120 skill sinh thành CSV ở bước data (mục 12), có cột: id, school, type, lv_req, cost, effects (công thức), cooldown, element.

### 6.3 Map, bãi săn, quái (15 vùng) [ĐỀ XUẤT]
Mỗi vùng: 3–4 bãi, 4–6 loại quái, 1 boss vùng; sinh tự động từ công thức 4.2 + template (không viết tay từng quái).

| # | Vùng | Level | Hệ chủ đạo | Ghi chú |
|---|---|---|---|---|
| 1 | Thanh Thảo Cốc | 1–10 | Mộc | Thú rừng, tutorial |
| 2 | Hắc Thạch Khoáng | 10–20 | Kim | Quặng, thợ mỏ |
| 3 | Hàn Thuỷ Đầm | 20–30 | Thuỷ | Thuỷ quái |
| 4 | Xích Sa Mạc | 30–40 | Hoả | Bọ cạp, hoả linh |
| 5 | Hoàng Thổ Cao Nguyên | 40–50 | Thổ | Thạch quái |
| 6 | Phong Lâm Cổ Đạo | 50–60 | Mộc/Kim | Sơn tặc |
| 7 | Vân Sương Hải Đảo | 60–70 | Thuỷ/Mộc | Hải tặc |
| 8 | Liệt Hoả Động | 70–80 | Hoả/Thổ | Dung nham |
| 9 | Ngân Sơn Tuyết Lĩnh | 80–90 | Kim/Thuỷ | Băng quái |
| 10 | Huyền Cơ Cổ Mộ | 90–100 | Hỗn hợp | Cuối giai đoạn trước chuyển sinh |
| 11 | Thiên Địa Mê Cung | 100–120 | Hỗn hợp | Sau chuyển sinh 1 |
| 12 | Hư Vô Uyên | 120–140 | Hỗn hợp | |
| 13 | Cửu U Hoang Nguyên | 140–160 | Hỗn hợp | |
| 14 | Thiên Cung Phế Tích | 160–180 | Hỗn hợp | |
| 15 | Hỗn Nguyên Cảnh | 180–200 | Hỗn hợp | |
Ngoài ra: **Vô Tận Tháp** (dungeon vô hạn, tầng tăng độ khó) là sink vật phẩm cuối game.
Tên vùng là placeholder; ID `zone_01`…`zone_15`. Phân wave: zone_01–11 (Wave 1), zone_12–13 (Wave 2), zone_14–15 (Wave 3), xem 12.5. Vùng 4 (sa mạc) và vùng 9 (tuyết) cần Việt hoá địa lý (phụ lục 16.4).

### 6.4 State machine thành viên
`idle → (chọn việc) → [đi bãi → hunting → nhặt đồ] → (túi đầy | HP thấp | đói | mệt | hết thuốc) → returning → [bán đồ → mua đồ → ăn → nghỉ → chữa trị] → idle`. Trạng thái đặc biệt: `injured`, `dead(chờ hồi sinh)`, `boss_raid`, `bounty`, `training`, `away(rời bang)`.
- Chọn việc bằng Utility AI (mục 9.1): cân nhắc level, hệ bãi, nhu cầu (đói, mệt, cần đồ), lệnh người chơi ghi đè.
- Người chơi có thể chạm vào thành viên để ra lệnh trực tiếp (mua đồ, học skill, đi chữa…) như EHT.

### 6.5 Boss Hoàng Kim (mỗi 1 giờ) — cả bang cùng đánh [CHỐT]
- Boss ngẫu nhiên (hệ, cấp theo cấp bang). Thành viên tập trung đánh; đồ rơi thuộc **bang** → hiện ở Chợ Bang: thành viên mua bằng tiền hoặc bang chủ **chỉ định trao**.
- Đội hình: gợi ý theo khắc hệ + vai trò (Utility AI, Premium có "Tự động xếp đội").
- Offline: boss bỏ lỡ gom thành "boss tồn đọng" (tối đa N), mô phỏng thống kê khi mở lại.
- Cộng thêm **Triệu Tập Lệnh** (tương tự "Field Boss horn" của EHT): vật phẩm để chủ động gọi boss.

### 6.6 Kinh tế
- Hai tầng tiền: tiền thành viên và quỹ bang. Tiền thành viên dư → mua tài nguyên độc quyền bang (vật phẩm boss hoàng kim, tiên thảo lộ, quế hoa tửu, thuỷ tinh, bí kíp, ngựa…). Bang thu thuế/phí giao dịch.
- Sink: **đã thiết kế ở mục 19** (thuốc, buff ăn/uống, cường hoá, thuế và phí duy trì bang, phí công trình, chuyển sinh).
- Tiền cao cấp ("Linh Bảo"): nhận từ nhiệm vụ/thành tựu; **không bán bằng tiền thật ở bản Free** trừ khi bạn muốn [MỞ].

### 6.7 Tuyển mộ
- Thụ động: ứng viên tự đến, tốc độ/độ hiếm theo Tụ Nghĩa Đường + danh vọng.
- Chủ động: gửi thiệp mời, dùng **Chiêu Hiền Lệnh** (tương tự "invite top-tier hunters with items" của EHT), Thám Tử Quán tìm người, thấy PA gần đúng.
- Ứng viên: hệ, phái (hoặc không), level (10 hoặc 0), sao/khoảng PA, tính cách bề mặt, yêu cầu (lương/đồ).

### 6.8 Giữ chân, rời bang, đàm phán
- `loyalty`, `mood` chịu ảnh hưởng của thuế, chia đồ, bị thương, ăn uống/nghỉ, trait, quan hệ trong bang.
- Loyalty thấp → **đòi rời** + điều kiện ở lại (tăng lương, món đồ cụ thể, xây công trình, đổi bãi). Người chơi: chấp nhận / phản đề xuất (xác suất theo trait) / để đi.
- Phản ứng dây chuyền nhẹ: người thân thiết với người rời bị giảm mood.

### 6.9 Đổi phái
- Thực hiện tại Tàng Kinh Các: tốn vật phẩm + thời gian + **mất % điểm skill** (giữ phần nhỏ), đổi hệ theo phái mới. Gắn với Tier chuyển sinh: lần đầu mỗi vòng chuyển sinh được miễn phí (xem 6.10).

### 6.10 Chuyển sinh (nội dung mới) [ĐỀ XUẤT]
Level cap tăng theo lần chuyển sinh, khớp thang CA tối đa 200:

| Lần | Điều kiện | Level cap mới | Giữ lại | Phần thưởng | Chi phí |
|---|---|---|---|---|---|
| 1 | lv 100 | 120 | 50% skill, toàn bộ trang bị | +1 slot trait lộ, mở skill bí kíp 1, đổi phái miễn phí 1 lần, +10% XP | 1 Chuyển Sinh Đan |
| 2 | lv 120 | 140 | 55% skill | +PA hiệu dụng cho tốc độ, mở Vô Tận Tháp tầng cao | 2 đan + vàng |
| 3 | lv 140 | 160 | 60% | mở bí kíp 2, +drop rate | 3 đan + vàng |
| 4 | lv 160 | 180 | 65% | +1 slot trait, +XP | 4 đan + vàng |
| 5 | lv 180 | 200 | 70% | kích hoạt "Phi Thăng" | 5 đan + vàng |
| Phi Thăng | lv 200, CA ≥ 180 | — | — | Thành viên trở thành **Trưởng Lão**: không đi săn nữa, cho buff toàn bang (theo phái/trait); bang có thêm slot Trưởng Lão theo cấp | vật phẩm đặc biệt |
Phi Thăng tạo vòng chơi vô hạn: bang liên tục nhận người mới và "tốt nghiệp" người cũ thành buff vĩnh viễn.
Chuyển sinh Đan: rơi từ Boss Hoàng Kim và chế ở Linh Miếu.

### 6.11 Giang Hồ & bang NPC [ĐỀ XUẤT — bạn đã đồng ý hướng cục bộ trước]
- **Bang NPC**: 8–12 bang chạy cục bộ ở mức thô (không mô phỏng realtime): mỗi bang có cấp, danh vọng, đội hình đại diện (snapshot tính bằng công thức), tăng trưởng theo thời gian thực/offline.
- **Danh sách Giang Hồ (free agents)**: thành viên rời bang vào danh sách này N ngày; bang NPC có thể "mời" họ (offer: lương, đồ, danh vọng). Người chơi có thể giữ lại, mời lại (offer/đàm phán), hoặc để họ vào bang NPC (họ trở thành đối thủ ở Lôi Đài).
- **Cố nhân trở lại**: người đã rời có thể quay lại qua chuỗi sự kiện cốt truyện (điều kiện: loyalty nền, thời gian, sự kiện); nhớ lại một phần skill/trait đã học ở bang bạn.
- **Lôi Đài** (Wave 2): đấu bang NPC bằng mô phỏng nhanh headless → thưởng danh vọng/vật phẩm. Bảng xếp hạng Lôi Đài chỉ cục bộ (tránh gian lận cloud).
- **Cloud bất đồng bộ** (Wave 4, tuỳ chọn): upload snapshot đội hình, người khác đấu với "bóng"; cần anti-cheat + kiểm duyệt, chưa cam kết.

### 6.12 Party (đội hình) [CHỐT ý tưởng; chi tiết là ĐỀ XUẤT]
**Quy tắc đã chốt:** khi luyện, thành viên có thể lập party, tối đa 5 người; ưu tiên mỗi party có 1 thành viên buff/hỗ trợ.
- **Vai trò**: tank, buff/hỗ trợ (hồi máu, buff), melee DPS, ranged DPS, khống chế/debuff. Phái buff/hỗ trợ ở Wave 1 là `moc_1`; ở Wave 2 thêm `thuy_2` (và các phái khác).
- **Ghép đội tự động** (Utility AI, bật ở cả Free và Premium): điểm ghép gồm: có buffer (+thưởng lớn), bù vai trò (tank + DPS), tương sinh ngũ hành giữa các thành viên, độ lệch level ≤ ngưỡng (ví dụ ±10), cùng bãi mục tiêu, quan hệ/trait hợp nhau. Bãi sẽ chọn theo hệ chủ đạo khắc/không bị khắc bởi đội.
- **Đội thiếu buffer**: vẫn chạy được nhưng hiệu suất thấp hơn (mất thưởng buffer). UI cảnh báo "thiếu buffer" và gợi ý tuyển phái buff (Thám Tử Quán lọc theo vai trò).
- **Tối ưu thêm (Premium)**: tự động xếp đội tối ưu, lưu cấu hình đội (preset), khoá/ghim thành viên. Ở Free vẫn có ghép đội tự động cơ bản và chỉnh tay.
- **Hiệu ứng đội** [ĐỀ XUẤT, chỉnh bằng simulator]:
  - Thưởng XP đội: `xp_mult = 1 + 0.08·(n−1)` (n ≤ 5), cộng +0.10 nếu có buffer, +0.05 nếu có tank.
  - Chuỗi tương sinh trong đội: +% sát thương/phòng thủ nhỏ.
  - Phủ khắc hệ: nếu ít nhất 1 thành viên khắc hệ của bãi/boss → thưởng sát thương.
  - Aggro: tank thu hút mục tiêu; buffer ưu tiên hồi máu người HP thấp nhất.
- **Chia đồ trong đội**: đồ phù hợp phái/hệ của thành viên nào thì ưu tiên thành viên đó; còn lại bán cho bang (như 6.4). Luật chia (`loot_rule`) chỉnh được theo bang.
- **Quan hệ**: ở cùng đội lâu → tăng "thân thiết", ảnh hưởng loyalty/mood (6.8): đội hợp thì tăng gắn bó, đội xung đột trait thì giảm.
- **Offline**: tính vào mô phỏng thống kê bằng hệ số thành phần đội (10).
- **Raid Boss Hoàng Kim** (6.5, 6.13): cả bang cùng đánh; các party giữ nguyên đội hình, thành viên chưa vào party được gom thành đội tạm.
- Schema: `Party` ở 4.1; thành viên có thêm `party_id`, trạng thái `in_party`.

### 6.13 Raid cả bang [CHỐT ý tưởng; chi tiết là ĐỀ XUẤT]
- **Tham gia**: mọi thành viên đủ điều kiện (không bị thương/chết/đang đi xa, đủ level tối thiểu của boss) đều tham gia. Thành viên đang hunting được gọi về, có thời gian tập hợp; có thể tắt cho từng người (ví dụ khi nghỉ).
- **Boss co giãn theo số người**: `boss_hp = base_hp(level) × (1 + hp_per_participant × số_người)`, cột `hp_per_participant` trong `golden_bosses.csv`; thành viên mạnh/yếu đều có chỗ.
- **Cấu trúc đội trong raid**: giữ nguyên party hiện có; người ngoài party được ghép thành đội tạm (cùng thuật toán 6.12). Mỗi đội có vai trò của mình (tank thu aggro, buffer hồi/buff, DPS…).
- **Phần thưởng theo đóng góp**: điểm đóng góp = sát thương gây ra + hồi máu + chịu sát thương (đã chuẩn hoá theo level) + hỗ trợ khống chế. Đồ rơi thuộc bang, phân phối ở Chợ Bang hoặc chỉ định trao (như 6.5); thưởng cá nhân (XP, vàng) theo điểm đóng góp, người ít đóng góp vẫn nhận phần tối thiểu.
- **Chết/bị thương**: người chết trong raid về Linh Miếu; bị thương nặng theo luật 6.4; người chết sớm vẫn được tính điểm đã đóng góp.
- **Hiệu năng mobile (quan trọng)**: tối đa vài chục thành viên cùng một trận realtime là nặng với điện thoại. Đề xuất: (1) mô phỏng chiến đấu chi tiết **toàn bộ** trong Simulation Core, nhưng hiển thị đầy đủ sprite/hiệu ứng chỉ cho nhóm nhỏ quanh camera (ví dụ ≤ 15 sprite đầy đủ, còn lại là hình thu gọn/đại diện theo đội); (2) giảm tần suất cập nhật AI cho thành viên ngoài khung; (3) giới hạn số damage number, hiệu ứng. Cần đo trên máy thật ở GĐ1 (vertical slice) trước khi chốt trần số thành viên mỗi bang.
- **Offline**: raid bỏ lỡ (mục 6.5) giải bằng mô phỏng thống kê dựa trên tổng chiến lực bang so với boss.
- **Ý nghĩa cho thiết kế**: bang chủ thấy rõ giá trị của đội hình cân bằng (mỗi đội có buffer), và cấp bang quyết định tối đa số người và độ khó boss.

## 7. Bản đồ tính năng EHT → công trình mới
Nguồn EHT: trang Zendesk chính thức của game (Building Information) + các guide (pocketgamer, gamingonphone, supercheats).

| EHT | Chức năng gốc | Bản của bạn (tên tạm) | Ghi chú |
|---|---|---|---|
| Town Hall | Mở khoá/nâng cấp công trình | **Tổng Đàn** | Cấp bang, giới hạn thành viên/công trình |
| Trading Post | Yêu cầu vật liệu, hunter đi nhặt rồi bán | **Thương Hội** | Đặt đơn vật liệu → thành viên đi săn theo đơn |
| Bounty Hut | Nhiệm vụ săn quái chỉ định, thưởng gold/exp | **Cáo Thị Đường** | Cũng là nguồn nhiệm vụ ngày/tuần |
| Restaurant | Bán đồ ăn (độ no) | **Thiện Đường** | |
| Tavern | Đồ uống lạnh | **Tửu Lâu** | Quế hoa tửu, mood/loyalty |
| Inn | Nghỉ ngơi (thể lực) | **Khách Điếm** | |
| Infirmary | Chữa thương | **Y Quán** | |
| Training Ground | Luyện tập mạnh hơn | **Luyện Công Phòng** | |
| Blacksmith | Chế vũ khí, giáp | **Thiết Tượng Phô** | |
| Jeweler | Chế phụ kiện | **Châu Bảo Các** | Thuỷ tinh, phụ kiện |
| Alchemist's Home | Chế thuốc | **Dược Quán** | Tiên thảo lộ, thuốc |
| Weapon/Armor/Accessory/Potion Shop | Bán trang bị đã chế | **Chợ Bang** (4 sạp thành 1 công trình) | **Gộp** để giảm art/scene cho dev solo |
| Academy | Học skill/trait | **Tàng Kinh Các** (skill) + **Ngộ Đạo Đài** (trait) | Đổi phái cũng ở đây |
| Enhancement Forge | Cường hoá trang bị | **Luyện Khí Đài** | |
| House | Tăng sức chứa | **Trú Xá** | Giới hạn thành viên (cùng Tổng Đàn) |
| Buff: Bank | Buff | **Tiền Trang** | Lãi quỹ bang |
| Buff: Courage Headstone | Buff | **Chiến Công Bi** | Buff chiến đấu |
| Buff: Fountain of Life | Buff | **Linh Tuyền** | Hồi/ HP tối đa |
| Buff: Library of Wisdom | Buff | **Tàng Thư Lâu** | XP/ngộ tính |
| Sanctuary/Statue of Resurrection | Hồi sinh, chuyển sinh (lv100) | **Linh Miếu** | |
| Dungeon | Mật cảnh có vật liệu hiếm | **Vô Tận Tháp** | |
| Field Boss (horn) | Triệu hồi boss | **Triệu Tập Lệnh** + Boss Hoàng Kim mỗi giờ | |
| PvP (Colosseum) | Đấu với hunter của town khác | **Lôi Đài** | Đấu bang NPC mô phỏng cục bộ (Wave 2, mục 6.11); cloud bất đồng bộ làm sau |
| Quest/Achievement | Hướng dẫn tiến trình | Nhiệm vụ chính + Thành tựu | Có cốt truyện quay lại cố nhân |
| Decor | Trang trí | Trang trí bang | Cosmetic, chỗ bán IAP |
| Hunter classes (4) + tier ngẫu nhiên | | 10 phái + PA (độ hiếm) | |
| Class change (cuối game) | | Đổi phái (6.9) | |
| Map: Town + 3 vùng + Hell Outpost | | 15 vùng (6.3) | |
Các công trình mới thêm (không có trong EHT): **Thám Tử Quán** (đánh giá PA, tìm người), **Mã Phòng** (ngựa), **Thuỷ Tinh Các** (nếu tách khỏi Châu Bảo Các), **Giang Hồ Ký Quán** (nhật ký/AI, mục 9).

## 8. Bảng xếp hạng, cloud, backend

### 8.1 Backend đề xuất: **Supabase** (Postgres + Auth + Edge Functions) [ĐỀ XUẤT]
| Tiêu chí | Supabase | Firebase | PlayFab |
|---|---|---|---|
| Tích hợp Godot | REST/HTTP trực tiếp, không cần SDK engine | Cần plugin cộng đồng cho Godot | REST, ít tài liệu cho Godot |
| Leaderboard | SQL view/index, xếp hạng bang/thành viên, theo mùa dễ | Cần tự dựng bằng Firestore/Functions | Có sẵn, hợp lý |
| Cloud save | Bảng + JSONB/Storage, có RLS | Firestore/Storage | Player Data |
| Anti-cheat cơ bản | Edge Function kiểm tra hợp lý | Cloud Functions | CloudScript |
| Chi phí | Gói free để dev; gói trả phí khi chạy thật (kiểm tra giá/giới hạn hiện hành) | Có free tier, Functions cần gói trả theo mức dùng | Free tier theo MAU |
Lý do chọn: ít phụ thuộc plugin, SQL hợp với bảng xếp hạng, ít code backend. Bạn có thể đổi nếu muốn (kiến trúc đã tách `CloudService`).
- Đăng nhập: Google (Android), Apple (iOS, bắt buộc nếu có đăng nhập mạng xã hội khác), có chế độ khách; liên kết tài khoản để chuyển thiết bị.
- Cloud save: 1 slot hoạt động; xung đột → người chơi chọn bản.
- Bảng xếp hạng: Bang hội (danh vọng/cấp), Thành viên (CA, level, số boss hạ), theo mùa. Gửi lên server bản tóm tắt có chữ ký + seed, server kiểm tra ngưỡng tăng trưởng hợp lý theo thời gian chơi (chống gian lận mức vừa đủ).
- Bản Free và Premium dùng chung bảng xếp hạng.

### 8.2 Save cục bộ
JSON nén có `version` + migration, checksum, ghi atomic (file tạm → rename), backup xoay vòng.

## 9. Lớp AI

### 9.1 Không-LLM (luôn bật)
- Utility AI / behavior tree cho hành vi thành viên; gợi ý xếp đội boss theo khắc hệ; cân bằng độ khó thích nghi.

### 9.2 LLM local (tuỳ chọn, gói tải thêm)
| Tính năng | Vai trò | Fallback khi tắt |
|---|---|---|
| Tiểu sử thành viên | Viết lý lịch/lời thoại từ trait + phái + hệ + history | Template + ghép mảnh |
| Giang Hồ Ký | Kể lại log bang thành văn | Câu mẫu từ log |
| Quân sư NPC | Giải thích gợi ý (số liệu do game tính) | Bảng gợi ý |
| Sự kiện ngẫu nhiên | Lời thoại cho sự kiện do game sinh | Kịch bản có sẵn |
| Đàm phán/mặc cả | Lời thoại theo tính cách; **kết quả do game quyết** | Hộp thoại cố định |
- Nguyên tắc: game logic deterministic; LLM chỉ sinh văn bản trong khung (template + placeholder + output giới hạn/JSON), kết quả được cache vào save.
- Kỹ thuật: llama.cpp (GGUF Q4) qua GDExtension, model 0.5–1.5B, tải thêm 300 MB–1 GB; chạy khi rảnh (không trong lúc cao tải), tự tắt nếu RAM thấp.
- Ngôn ngữ: tiếng Anh tốt hơn tiếng Việt ở model nhỏ → mặc định dùng template; LLM bổ sung "văn phong" cho phần phụ; test chất lượng vi/en riêng.
- AI nằm trong bộ tính năng nâng cao của Premium [XÁC NHẬN].

## 10. Offline progress
- `Δt = now − last_save`; cap mặc định 8h (Free) / 24h (Premium) [ĐỀ XUẤT]; dùng giờ server khi có mạng, chặt hơn khi hoàn toàn offline (chống chỉnh đồng hồ).
- Không mô phỏng từng tick; dùng thống kê kỳ vọng/giờ cho từng thành viên (level, CA, trang bị, bãi, hệ) + phương sai nhẹ từ RNG có seed; xử lý các sự kiện rời rạc (túi đầy, thuốc, bị thương, boss tồn đọng).
- Màn hình "Báo cáo lúc bạn vắng mặt".

## 11. Mô hình Free / Premium [ĐỀ XUẤT]

### 11.1 Hình thức phát hành
**Một app + mở khoá Premium bằng mua một lần (IAP, non-consumable)** thay vì hai app riêng: một codebase, một cloud save, nâng cấp không mất dữ liệu, dễ quản lý store. [CHỐT]. **PC (Steam)**: chỉ bản trả phí, không quảng cáo, tính năng Premium mở sẵn; dùng chung tài khoản cloud (Supabase); PA chính xác bán theo cùng cơ chế (mục 11.5, qua Steam IAP/DLC).

### 11.2 Bảng so sánh
| | Free | Premium |
|---|---|---|
| Vòng lặp chính (săn, công trình, boss, chuyển sinh, tuyển mộ) | Đầy đủ | Đầy đủ |
| Quảng cáo | Banner dưới màn hình; quảng cáo thưởng (rewarded) **tuỳ chọn** qua nhiệm vụ | Không quảng cáo |
| Nhiệm vụ ngày/tuần | Có; mục "xem quảng cáo nhận thưởng" | Có; mục đó nhận thưởng trực tiếp, không xem quảng cáo |
| Tính năng nâng cao | Khoá | Mở (gợi ý bên dưới) |
Tính năng nâng cao gợi ý: tự động xếp đội boss, thao tác hàng loạt, thống kê chi tiết/phân tích bang, cap offline cao hơn, thêm slot cloud save, gói AI (mục 9.2), theme/trang trí, thêm lượt tuyển mộ/ngày. (**Xem PA chính xác bán riêng**, không nằm trong Premium: mục 11.5.)
- Nguyên tắc: không bán sức mạnh trực tiếp làm lệch bảng xếp hạng; không dùng quảng cáo xen kẽ (interstitial) làm gián đoạn gameplay.

### 11.3 Kỹ thuật
- `Entitlement` service: `is_premium`, kiểm tra bằng receipt store + cache cục bộ + đồng bộ qua tài khoản cloud; mọi tính năng khoá đi qua `FeatureFlags`.
- Ads: banner cố định dưới (tính vào layout UI từ đầu), rewarded ads gắn vào quest; tuân thủ đồng ý quảng cáo (UMP/GDPR), ATT trên iOS, phân loại độ tuổi trên store.

### 11.4 Nhiệm vụ ngày/tuần [CHỐT cách hiểu: xem quảng cáo thưởng là tuỳ chọn ở Free, Premium nhận thẳng]
- Ngày (5–6 nhiệm vụ): săn N quái, hạ boss hoàng kim, bán X vật phẩm, thu nhận ứng viên, đăng nhập, **xem 1 quảng cáo (Free) / nhận thẳng (Premium)**.
- Tuần (4–5): chế tạo, nâng cấp công trình, đạt mốc CA, hoàn thành chuỗi bounty, hạ boss tồn đọng.
- Thưởng: vàng, Linh Bảo, vật phẩm tuyển mộ, nguyên liệu chuyển sinh (giới hạn để không phá cân bằng).

### 11.5 Bán riêng: xem PA chính xác [ĐỀ XUẤT — chờ bạn chốt số lượng]
Hai sản phẩm khác nhau, cùng tồn tại:

| | Thiên Cơ Kính | Thiên Nhãn |
|---|---|---|
| Loại | Vật phẩm tiêu hao (consumable) | Mở khoá vĩnh viễn (non-consumable) |
| Tác dụng | Mở PA chính xác của **1 thành viên** (lưu vĩnh viễn trên thành viên đó) | Mở PA chính xác của **mọi thành viên**, hiện tại và tương lai |
| Giá | Thấp mỗi lượt; mua theo gói | Cao, mua một lần |
| Có thể nhận miễn phí | Có, rất ít (bên dưới) | Không bao giờ |
| Hợp với | Người chỉ muốn xem vài thành viên quan trọng | Người chơi sâu, tuyển mộ lâu dài |
Lý do có cả hai: Kính dễ mua thử; Nhãn là gói "trọn đời". Giá Nhãn nên tương đương số Kính một người chơi sâu thường dùng hết vòng đời (tính bằng simulator: một bang trung bình đi qua bao nhiêu ứng viên).

**Quy tắc để nhiệm vụ miễn phí không làm mất giá Premium và doanh thu PA:**
- Premium **không** bao gồm Kính/Nhãn, và Kính/Nhãn không thay thế giá trị Premium (không quảng cáo, tự động xếp đội/tối ưu, thống kê, cap offline, AI…). Hai thứ độc lập nên không cạnh tranh nhau.
- Nguồn Kính miễn phí [ĐỀ XUẤT]: 1 Kính/tuần qua nhiệm vụ tuần + thưởng đơn lẻ ở vài mốc (chuyển sinh, thành tựu); tồn kho tối đa 5 để không tích trữ. Free và Premium nhận **như nhau**.
- Thưởng của nhiệm vụ xem quảng cáo **không bao giờ** là Kính/Nhãn.
- Không phát vĩnh viễn miễn phí các tính năng của Premium qua nhiệm vụ; chỉ cho **dùng thử có giới hạn** (ví dụ tự động xếp đội 24 giờ, vài lần) để người chơi thấy giá trị.
- Kỹ thuật: entitlement tách khỏi `is_premium`; consumable không khôi phục được từ store nên số dư phải lưu trong cloud save, xác thực receipt qua Edge Function; non-consumable dùng "Restore purchases". Steam: DLC/IAP tương đương.

## 12. Phạm vi MVP & lộ trình (dev solo)

### 12.1 Spike kỹ thuật (tuần 1–2) — quyết định engine
Prototype tối giản trên máy thật: Godot + AdMob banner/rewarded + IAP non-consumable + Google Sign-In + gọi REST Supabase (lưu/đọc save, bảng xếp hạng) + chạy thử llama.cpp model nhỏ. Nếu thất bại ở nhiều điểm → chuyển Unity.
- **Android trước, iOS sau** [CHỐT]: Android cần tài khoản Google Play Console (phí một lần) và nên có máy Android thật. iOS simulator đủ để dev UI/gameplay, nhưng **không đủ** để test IAP thật, Sign in with Apple, quảng cáo thật và TestFlight → cần Apple Developer Program (phí hằng năm) và thiết bị thật trước khi phát hành iOS. Phần iOS trong spike được ghi nhận "chưa kiểm chứng".
- **Spike art** (cùng giai đoạn): làm thử 1 nhân vật paper-doll hoàn chỉnh (idle/chạy/đánh/bị thương) bằng pipeline AI ở mục 12.4 để biết có đạt chất lượng và nhất quán không.

### 12.2 Giai đoạn
| GĐ | Nội dung | Kết quả |
|---|---|---|
| 0 | Spike kỹ thuật + Simulation Core headless (1 phái, 3 bãi, loot, kinh tế) + balance sim | Số liệu sơ bộ |
| 1 | Vertical slice: map realtime, 3 phái, 1 bãi, 1 boss, 5 công trình, save/load | Chơi 30–60 phút |
| 2 | Core loop: tuyển mộ, CA/PA, trait, Chợ Bang, thuế, offline progress, nhiệm vụ | Vòng lặp hoàn chỉnh |
| 3 | Nội dung Wave 1 (5 phái, 11 vùng, chuyển sinh 1, giữ chân/rời bang); các wave sau xem 12.5 | Nội dung ra mắt |
| 4 | Services: cloud save, leaderboard, ads, IAP, Free/Premium | Beta |
| 5 | AI pack + localization vi/en + polish + QA thiết bị | Release candidate |
| 6 | Phát hành Android → iOS (khi có Apple Developer) → PC/Steam (bản trả phí) → Web | |
**Ra mắt theo wave nhưng plan đầy đủ cho tất cả ngay từ đầu** [CHỐT]: xem 12.5.

### 12.3 Pipeline nội dung
Excel/Google Sheet → CSV/JSON → `content_validator` (kiểm tra id, tham chiếu, cân bằng) → game. Sinh quái/bãi/skill bằng script từ template.

### 12.4 Pipeline art với công cụ AI [CHỐT dùng AI; quy trình là ĐỀ XUẤT]
Rủi ro cần xử lý (kiểm tra lại chính sách hiện hành vì thay đổi thường xuyên):
- **Bản quyền**: ở nhiều nơi (ví dụ Mỹ), tác phẩm do AI tạo hoàn toàn có thể không được bảo hộ bản quyền → khó chống sao chép art. Cách giảm: chỉnh sửa/vẽ lại đáng kể bằng tay, lưu lịch sử chỉnh sửa và prompt.
- **License công cụ**: chỉ dùng công cụ cho phép dùng thương mại; lưu bằng chứng (điều khoản, ngày, gói trả phí).
- **Nền tảng phân phối**: Steam yêu cầu khai báo việc dùng nội dung AI; Google Play/Apple có chính sách riêng. Kiểm tra trước khi nộp.
- **Không dùng tên nghệ sĩ/IP trong prompt**; không tạo nhân vật giống IP có sẵn.
- **Chất lượng pixel**: AI thường không giữ lưới pixel, palette, kích thước sprite và animation nhất quán.
Quy trình:
1. Khoá **palette chung** (ví dụ 32–48 màu, chia theo hệ) và kích thước sprite (ví dụ 32×32 hoặc 48×48).
2. **Nhân vật = paper-doll**: thân base (vẽ/chỉnh tay chuẩn 1 lần) + lớp trang phục/vũ khí theo phái + palette swap. AI dùng nhiều nhất cho: icon vật phẩm (hàng trăm), chân dung ứng viên, tile/nền map, trang phục, vật phẩm trang trí, UI icon.
3. Hậu xử lý bắt buộc: hạ độ phân giải → quantize về palette → dọn tay trong Aseprite (hoặc tương đương).
4. Animation tối thiểu: idle 2 khung, chạy 4, đánh 4, bị thương 1, chết 3; dùng lại giữa các phái.
5. **Việt hoá chi tiết văn hoá bằng tay**: trang phục, kiến trúc, binh khí thời kỳ lịch sử (áo giao lĩnh, áo tứ thân…) AI hay sai chi tiết; cần tài liệu tham khảo và kiểm tra thủ công.
6. Âm thanh/nhạc: nếu dùng AI cũng áp dụng cùng nguyên tắc license + khai báo.

**Phân công: phần nào Claude làm được, phần nào cần công cụ ngoài** [ĐỀ XUẤT]
- **Claude không tạo được pixel art chất lượng game** như công cụ sinh ảnh chuyên dụng. Art cuối cùng cần công cụ AI sinh ảnh bên ngoài + bước dọn pixel.
- **Claude làm được**: art bible (palette, kích thước, quy tắc nét/bóng, danh sách asset cần có), prompt template cho từng loại asset, script hậu kỳ (hạ độ phân giải, quantize về palette, snap lưới pixel, cắt/ghép sprite sheet, kiểm tra kích thước/palette), tool ghép paper-doll và palette swap theo hệ, và **placeholder art bằng code** (hình khối màu theo hệ/phái, icon 16×16 viết tay bằng ma trận pixel) để dev gameplay không phải chờ art.
- **Giảm phụ thuộc vào dọn tay**: style tối giản (ít chi tiết, ít màu), sprite nhỏ, animation ít khung, tự động hoá hậu kỳ càng nhiều càng tốt. Nếu bạn chưa quen Aseprite: Aseprite (trả phí), LibreSprite hoặc Pixelorama (miễn phí) đều đủ dùng; chỉ cần sửa lỗi nhỏ sau khi script đã quantize.
- **Chọn công cụ AI sinh ảnh** ở spike art (12.1): thử 2–3 công cụ, tiêu chí: (1) cho phép dùng thương mại, (2) dễ xuất nền trong suốt/độ phân giải thấp hoặc dễ quantize, (3) giữ nhất quán nhân vật/style qua ảnh tham chiếu, (4) giá. Chính sách và công cụ thay đổi nhanh nên chưa khẳng định công cụ cụ thể; có thể tra cứu lại bằng web search khi bạn bắt đầu spike.
- **[CHỐT] Không thuê artist, chỉ dùng AI miễn phí.** Hệ quả cần chấp nhận:
  - Gói miễn phí thường có giới hạn lượt/ngày, chất lượng thấp hơn, và **nhiều gói miễn phí không cho dùng thương mại, hoặc yêu cầu ghi công/giữ watermark, hoặc cấp quyền thương mại theo điều khoản riêng.** Đây là rủi ro lớn nhất với game bán thương mại: một asset sai license có thể bị gỡ khỏi store. Mình chưa tra cứu điều khoản hiện hành của từng công cụ nên không khẳng định công cụ nào an toàn.
  - Quy trình bắt buộc: với mỗi công cụ, lưu ảnh chụp trang điều khoản, ngày, tên gói tài khoản; ghi vào `ART_LICENSE_LOG.md` cho từng asset (công cụ, ngày, prompt, file đầu ra). Chỉ dùng công cụ có điều khoản cho phép thương mại ở đúng gói bạn đang dùng.
  - Chọn công cụ: Claude có thể tra cứu điều khoản hiện hành của vài công cụ bằng web search khi bạn bắt đầu spike art (bạn gọi thì mình làm).
  - Nhờ placeholder bằng code và pipeline hậu kỳ tự động (mục trên), game vẫn chạy được ngay cả khi chưa có art cuối; art AI thay dần từng nhóm asset.
  - Dự phòng nếu không công cụ miễn phí nào đủ chất lượng/license: giữ style tối giản bằng hình khối/sprite tự sinh bằng code, hoặc mua pack có license thương mại (không phải thuê artist).


#### 12.4.1 Kết quả tra cứu điều khoản công cụ AI (16/11/2026) — ĐỌC TRƯỚC KHI DÙNG
Tra bằng web search; nhiều nguồn là bài viết/diễn đàn, không phải điều khoản gốc. **Điều khoản đổi nhanh: trước khi tạo asset phải mở trang điều khoản gốc, chụp lại, ghi vào `ART_LICENSE_LOG.md`.** Đây không phải tư vấn pháp lý.

| Công cụ | Điều tra được | Đánh giá cho game bán thương mại |
|---|---|---|
| **Leonardo.ai** (gói miễn phí) | Trang hỗ trợ chính thức nói người dùng gói miễn phí được tải ảnh của mình để dùng thương mại, nhưng ảnh tạo ở gói miễn phí là **công khai** (người dùng khác xem/remix được) và Leonardo giữ quyền vĩnh viễn trên ảnh công khai. Quyền sở hữu đầy đủ chỉ nêu cho ảnh riêng tư ở gói trả phí | **Rủi ro vừa**: dùng được nhưng không độc quyền, người khác có thể lấy cùng ảnh; asset nhân vật chính không nên làm ở đây. Gói trả phí 1 tháng để làm hàng loạt asset quan trọng có thể đáng tiền (trái nguyên tắc "chỉ miễn phí" của bạn, bạn quyết) |
| **Microsoft Designer / Bing Image Creator** | Bình luận trích điều khoản Designer: "chỉ dùng cá nhân, không dùng trong kinh doanh/thương mại". Phản hồi của nhân viên hỗ trợ thì mơ hồ; Image Creator không cấm rõ nhưng không có cam kết thương mại | **Không dùng** cho game bán |
| **Stable Diffusion (chạy cục bộ) — Stability AI Community License** | Trang chính thức: miễn phí cho cá nhân/doanh nghiệp doanh thu dưới 1 triệu USD/năm; bạn sở hữu output, dùng thương mại tuân Acceptable Use Policy; license có thể bị thu hồi nếu vi phạm; vượt ngưỡng phải mua Enterprise; trường hợp nghiên cứu mà dùng cho sản phẩm thương mại phải đăng ký | **Phù hợp nhất về pháp lý** (không mất tiền, không công khai ảnh). Cần máy đủ mạnh (Mac của bạn chạy được nhưng chậm; chưa kiểm chứng) và nên dùng LoRA pixel-art có license rõ ràng; kiểm tra license của từng checkpoint/LoRA tải về |
| Flux, các mô hình mở khác | Chưa xác minh điều khoản trong lần tra này | Cần tra riêng từng model/phiên bản trước khi dùng |

Về bản quyền (nguồn: tóm tắt báo cáo Part 2 của US Copyright Office, 29/1/2025): chỉ prompt **không** đủ để được coi là tác giả; phần do người **tạo/chỉnh sửa** có tính sáng tạo, việc **chọn lọc và sắp xếp** thì được bảo hộ. Hệ quả cho dự án: art AI thuần tuý có thể không được bảo hộ nên khó chống sao chép; chỉnh sửa tay đáng kể (dọn pixel, vẽ lại, ghép paper-doll) vừa tăng chất lượng vừa tăng khả năng được bảo hộ.

Về nền tảng phân phối (từ bài viết pháp lý thứ cấp, **cần đối chiếu trang chính thức**): Steam bắt buộc khai báo nội dung AI tạo sẵn và cam kết không vi phạm IP; Google Play có chính sách riêng cho tính năng **AI sinh nội dung trong app** (phải có cách báo cáo nội dung xúc phạm ngay trong app, kiểm thử đầu ra) — áp dụng cho **LLM local tuỳ chọn** của game, không áp dụng cho art đã sinh sẵn.

**Khuyến nghị:** (1) Pipeline chính = Stable Diffusion cục bộ + LoRA pixel-art có license rõ + hậu kỳ tự động + dọn tay; (2) Leonardo gói miễn phí chỉ cho icon/nền phụ, ghi log; (3) loại Microsoft Designer; (4) khai báo AI khi nộp Steam; (5) thêm nút báo cáo nội dung ở tính năng LLM.
Nguồn: [Leonardo – Commercial usage](https://intercom.help/leonardo-ai/en/articles/8044018-commercial-usage) · [Microsoft Q&A – Designer/Image Creator](https://learn.microsoft.com/en-us/answers/a/11819498) · [Stability AI license](https://stability.ai/license) · [Akin Gump – USCO Part 2](https://www.akingump.com/en/insights/ai-law-and-regulation-tracker/us-copyright-office-releases-part-2-of-ai-report) · [Promise Legal – chính sách nền tảng](https://blog.promise.legal/ai-game-assets-copyright-platform-policy-2025/)

### 12.5 Kế hoạch theo wave (plan đầy đủ, ra mắt dần) [ĐỀ XUẤT; điều chỉnh so với v0.2]
Đã sửa: v0.2 ghi "10 vùng + chuyển sinh 1–2", nhưng chuyển sinh 1 cần vùng lv100–120 nên Wave 1 cần **11 vùng** và chỉ **chuyển sinh 1**.

| Wave | Phái | Vùng | Chuyển sinh / hệ thống | Ghi chú |
|---|---|---|---|---|
| 1 (ra mắt) | 5 phái, 1 mỗi hệ, đủ vai trò: `kim_2` (melee burst), `moc_1` (hồi máu), `thuy_1` (khống chế), `hoa_2` (ranged DPS), `tho_1` (tank) | zone_01–11 (lv 1–120) | Chuyển sinh 1; CA/PA, trait, tuyển mộ, giữ chân/rời bang, offline, Boss Hoàng Kim, nhiệm vụ, Free/Premium, cloud, BXH | Đủ vai trò để chơi raid; chỉ có `moc_1` là phái buff/hỗ trợ (xem 6.12, [MỞ] 2) |
| 2 | 5 phái còn lại: `kim_1`, `moc_2`, `thuy_2`, `hoa_1`, `tho_2` | zone_12–13 (lv 120–140) | Chuyển sinh 2–3, đổi phái đầy đủ, Lôi Đài (bang NPC), Vô Tận Tháp, bí kíp | |
| 3 | — | zone_14–15 (lv 140–200) | Chuyển sinh 4–5, Phi Thăng/Trưởng Lão | Hoàn thiện nội dung |
| 4 (tuỳ chọn) | — | — | Cloud PvP bất đồng bộ, sự kiện theo mùa | Chưa cam kết |

**Quy tắc để "plan cho tất cả" không gây làm lại:**
- Hoàn thành thiết kế dữ liệu cho cả 10 phái, 15 vùng, 5 lần chuyển sinh **trước ra mắt Wave 1** (CSV skill/trait/quái đã có và qua `content_validator`), nhưng khoá bằng cờ `content_wave`.
- Save schema và ID dành sẵn chỗ cho phái/vùng/chuyển sinh chưa mở; có migration cho từng wave.
- Mọi hệ thống lõi (mục 5–6, trừ Lôi Đài/Phi Thăng) chạy đủ ở Wave 1; các wave sau chỉ thêm dữ liệu và vài tính năng đã đặt chỗ.
- Chạy balance simulator cho toàn bộ 10 phái trước Wave 1 để biết các wave sau không phá cân bằng.

## 13. Rủi ro chính
- **Khối lượng nội dung/art** → paper-doll modular, palette swap, data-driven, phát hành theo đợt.
- **Cân bằng** → balance simulator từ GĐ0.
- **Plugin mobile trên Godot** → spike tuần 1–2, phương án B Unity.
- **LLM mobile** → luôn optional + fallback; kiểm tra RAM/pin/dung lượng.
- **IP** → xem mục 14.
- **Chống gian lận bảng xếp hạng** → chấp nhận mức vừa đủ.

## 14. IP & pháp lý (không phải tư vấn pháp lý)
- Làm mới tên phái/skill/item/map/NPC/art/âm thanh; không dùng "Võ Lâm", "JX1" làm tên game/thương hiệu.
- Học cơ chế EHT, không sao chép tên, art, bảng chỉ số, văn bản.
- Kiểm tra trùng lặp nhãn hiệu cho tên game và tên phái trước khi chốt (đặc biệt tên 10 phái đề xuất).
- Asset: dùng art tự làm / mua có license thương mại / thuê; lưu bằng chứng license. Nếu dùng công cụ sinh ảnh/âm thanh, kiểm tra điều khoản thương mại của công cụ.
- Chính sách quyền riêng tư + điều khoản (có cloud save, quảng cáo, analytics).
- Chủ đề lịch sử Việt Nam: xem lưu ý văn hoá ở phụ lục 16.3. Nên tra cứu quy định phát hành game tại Việt Nam và quy định từng store (mình chưa kiểm chứng; nên hỏi luật sư/cơ quan quản lý).

## 15. Câu hỏi còn mở
Đã chốt: tên, raid, nhịp chơi (hướng), hệ thống tiêu vàng (soạn xong), tra điều khoản AI art (bước đầu). Còn lại:
1. **Công cụ art cuối cùng**: bạn chọn pipeline nào ở 12.4.1 (Stable Diffusion cục bộ là đề xuất)? Mac của bạn là chip nào/RAM bao nhiêu (để biết chạy cục bộ nổi không)?
2. **Số liệu nhịp & kinh tế** (mục 4.3, 19): duyệt hoặc chỉnh sau khi chạy thử vertical slice; cần tích hợp skill thật và cường hoá vào mô phỏng (mục 20) rồi đo lại.
3. **Tên hiển thị cho 120 skill** và dữ liệu bang NPC: soạn khi vào giai đoạn 3.
4. **Hạn mức chi tiêu thật**: Linh Bảo có bán bằng tiền thật ở bản Free không? (6.6, hiện đề xuất KHÔNG).
5. **Bắt đầu code**: dùng bộ prompt mục 21; thứ tự khuyến nghị: S1–S5 (mở rộng lõi Python) song song P1 (spike Godot).

## 16. Phụ lục: Naming Brief (chủ đề lịch sử Việt Nam)

### 16.1 Nguyên tắc kỹ thuật
- Code và data chỉ dùng **ID bất biến**; tên hiển thị nằm trong `/i18n/names_vi.csv` và `/i18n/names_en.csv` (cột: `id, name, short, desc`). Đổi tên không đụng code, không đổi save.
- Cần đặt tên (vi + en) cho:
  - 10 phái: `kim_1, kim_2, moc_1, moc_2, thuy_1, thuy_2, hoa_1, hoa_2, tho_1, tho_2`.
  - 15 vùng: `zone_01`…`zone_15`.
  - 26 công trình: `bld_hq, bld_trade, bld_bounty, bld_restaurant, bld_tavern, bld_inn, bld_infirmary, bld_training, bld_smith, bld_jeweler, bld_alchemy, bld_market, bld_academy_skill, bld_academy_trait, bld_enhance, bld_housing, bld_bank, bld_buff_courage, bld_buff_life, bld_buff_wisdom, bld_shrine, bld_tower, bld_arena, bld_scout, bld_stable, bld_chronicle`.
  - Tiền tệ/vật phẩm đặc biệt: vàng, Linh Bảo, Chuyển Sinh Đan, Triệu Tập Lệnh, Chiêu Hiền Lệnh, Thiên Cơ Kính, Thiên Nhãn.
  - Danh hiệu: bang chủ, Trưởng Lão, các cấp bang.
- Tên game cũng cần đổi (tên tạm "JX1 Tycoon").

### 16.2 Các hướng chủ đề (để bạn chọn, không áp đặt)
- **A. Thời kỳ/địa danh lịch sử**: vùng săn theo các địa danh và giai đoạn dựng nước – giữ nước (ví dụ Văn Lang, Cổ Loa/Âu Lạc, Mê Linh, Bạch Đằng, Chi Lăng, Lam Sơn, Đống Đa…). Hợp với 15 vùng xếp theo level: càng sâu càng gần các giai đoạn "lớn".
- **B. Truyền thuyết/dân gian**: quái và boss lấy từ yêu tinh, thuỷ quái, linh vật dân gian (thuồng luồng, hồ tinh, ngư tinh, xà tinh…); ngũ hành khớp với các cặp đối lập kiểu Sơn Tinh – Thuỷ Tinh. Dễ tạo Boss Hoàng Kim đa dạng.
- **C. Võ cổ truyền Việt Nam**: phái dựa trên truyền thống võ (binh khí, quyền, thế võ theo vùng). Cần tra cứu kỹ trước khi dùng vì nhiều tên là tổ chức/môn phái có thật.
- **[CHỐT] Hướng A + B**: kết hợp A + B: vùng săn theo địa danh/thời kỳ lịch sử, quái và boss theo truyền thuyết dân gian, phái lấy cảm hứng từ truyền thống võ/binh pháp nhưng **tên do bạn tự đặt**, không dùng tên môn phái thật.
- Gợi ý từ khoá theo hệ (chỉ để khơi ý, không phải danh sách tên):
  - Kim: trống đồng, rìu/giáo đồng, kiếm, giáp, thành luỹ.
  - Mộc: rừng, thảo dược (nam dược), cung nỏ gỗ, làng quê.
  - Thuỷ: sông, đầm, sóng, triều, sương mù, thuyền chiến.
  - Hoả: lửa, tre, pháo, núi lửa, lò rèn.
  - Thổ: đê, thành đất, núi, đất đỏ bazan, thành luỹ.

### 16.3 Lưu ý văn hoá & pháp lý
- Nhân vật lịch sử thật và nhân vật tín ngưỡng: nên dùng với sự tôn trọng (NPC, Trưởng Lão, cốt truyện); **[CHỐT] quái và boss chỉ là quái thú/linh vật dân gian, không dùng nhân vật lịch sử/tín ngưỡng làm quái hay boss**; tránh nội dung có thể gây phản cảm. Cần tra cứu quy định/thông lệ về sử dụng hình ảnh nhân vật lịch sử và tín ngưỡng (mình chưa kiểm chứng).
- Kiểm tra tên môn phái/tên võ thật có phải nhãn hiệu hoặc tổ chức đang hoạt động không trước khi dùng.
- AI art hay sai chi tiết văn hoá (trang phục, kiến trúc, binh khí); phải có tài liệu tham khảo và kiểm tra thủ công (12.4).
- Giọng văn: chọn rõ phong cách (chính sử nghiêm túc hay huyền thoại giả tưởng) để toàn bộ tên và văn bản nhất quán, cũng giúp prompt cho LLM (mục 9.2).

### 16.4 Việt hoá địa lý các vùng placeholder
- Vùng 4 "Xích Sa Mạc" (sa mạc): Việt Nam không có sa mạc lớn; có thể chuyển sang vùng cát/đồi cát ven biển, hoặc vùng khô hạn miền Trung.
- Vùng 9 "Ngân Sơn Tuyết Lĩnh" (tuyết): đổi sang núi cao sương giá/mây mù (ví dụ vùng núi cao phía Bắc), quái "băng" thành quái "sương/mù".
- Phái thuỷ "Băng Tâm Viện" (băng, đóng băng): đổi chủ đề khống chế sang sóng, triều, sương mù, nước lũ; cơ chế "đóng băng" đổi thành "ngập/cuốn trôi" (làm chậm, đẩy lùi).
- Vùng 11–15 (hỗn hợp, level cao): tuỳ hướng chủ đề (ví dụ cõi truyền thuyết hoặc các thời kỳ sau trong lịch sử).

### 16.5 File mẫu để bạn điền (`names_vi.csv`)
```
id,name,short,desc
kim_1,,,
kim_2,,,
zone_01,,,
bld_hq,,,
```

## 17. Dữ liệu đã có (Wave 1–3) & công cụ
Toàn bộ nội dung cho cả 3 wave đã có; ra mắt dần theo cờ `wave`/`unlock_wave`. Validator: `python3 -I tools/content_validator.py` → **0 lỗi, 0 cảnh báo**.

### 17.1 File
| File | Nội dung |
|---|---|
| `data/schools.csv` | 10 phái (hệ, vai trò, vũ khí, wave, `buff_role`, `armor_class`) |
| `data/skills.csv` | 120 skill = 10 phái × 12 (4 chủ động lv1/10/20/30, 4 bị động lv5/15/25/40, 2 tuyệt kỹ lv60/100, 2 bí kíp lv100 chuyển sinh 1 / lv140 chuyển sinh 3); `unlock_wave = max(wave phái, wave chuyển sinh)` |
| `data/traits.csv` | 40 trait |
| `data/zones.csv` / `monsters.csv` / `grounds.csv` / `golden_bosses.csv` | 15 vùng, 75 quái (4 thường + 1 boss/vùng), 45 bãi săn, 15 boss Hoàng Kim |
| `data/materials.csv` | 45 nguyên liệu (3 phẩm cấp/vùng) |
| `data/items.csv` | 1043 vật phẩm: 21 bậc trang bị (level_req 1,10,20…100,110…200), độ hiếm thường/hiếm/sử thi; thuốc, đồ ăn; **mới**: `feast_*` (buff XP), `brew_*` (buff sát thương), `item_enhance_ward` |
| `data/recipes.csv` | 408 công thức (gồm tiệc, rượu, bùa hộ cường); công trình cấp `ceil(bậc/2)` |
| `data/drop_tables.csv` | 315 dòng; `equip_pool` lọc theo độ hiếm + khoảng level |
| `data/buildings.csv`, `building_meta.csv` | 26 công trình, 236 dòng cấp, `hq_lv_req`, cấp tối đa |
| `data/quests.csv` | 12 nhiệm vụ ngày/tuần; nhiệm vụ quảng cáo không bao giờ thưởng Kính/Nhãn; tuần hoàn thành tất cả = 1 Thiên Cơ Kính |
| `data/rebirth.csv` | 5 lần chuyển sinh + Phi Thăng (trần 100/120/140/160/180/200) |
| `data/enhance.csv` | **Mới**: bảng cường hoá +1…+20 (tỉ lệ, hệ số giá, hình phạt, chỉ số cộng) |
| `data/config.csv`, `sim_params.csv`, `sim_roles.csv` | Tham số game (gồm nhịp XP, tiêu hao, thuế, cường hoá) và núm chỉnh mô phỏng |
| `i18n/names_*.csv`, `names_items_*.csv` | Tên VI/EN cho phái, vùng, boss, công trình, ~1080 vật phẩm. Tên bậc tiệc/rượu/thuốc là tên tạm "Bậc N"; chưa có tên hiển thị cho skill |
| `tools/` | `content_validator.py`, `calibrate.py`, `balance_sim.py`; `gen_a.py`, `gen_b.py`, `gen_c.py` sinh dữ liệu (`gen_a` GHI ĐÈ khi chạy lại; `gen_b`, `gen_c` idempotent) |
| `sim/` | Lõi mô phỏng Python: `rng, data, formulas, model, hunt, offline, raid, economy` |
| `tests/test_core.py` | 22 unit test |

### 17.2 Ghi chú
- Tên (hướng A+B) đã được duyệt. Chi tiết truyền thuyết/địa danh trong mô tả chưa tra nguồn; tên phái/vùng cần kiểm tra nhãn hiệu.
- ID bất biến; thêm nội dung chỉ cần thêm dòng CSV.
- `buff_role=true` ưu tiên ghép buffer cho party; Wave 1 chỉ có `moc_1` → tăng tỉ lệ ứng viên `moc_1` + vật phẩm Lệnh Kỳ (phương án A đã chốt).

## 18. Lõi mô phỏng tham chiếu & kết quả cân bằng
### 18.1 Phạm vi
Sandbox không có Godot nên lõi tham chiếu viết bằng **Python** (`sim/`), để port sang GDScript theo `GODOT_PORT.md`. Gồm: RNG PCG32 tất định (khớp vector chuẩn), chiến đấu hướng sự kiện, săn theo chuyến (túi riêng mỗi thành viên), party, raid cả bang, offline fast-forward lấy mẫu (mặc định chunk 2 giờ, 4 mẫu: lệch ~1% XP, nhanh hơn chạy chính xác vài lần), nhịp XP (đầu nhanh, chuyển sinh chậm dần) và mô hình kinh tế giải tích (`economy.py`: thu nhập, tiêu hao, cường hoá Markov có kiểm chứng bằng mô phỏng). 22 unit test qua. **Chưa có**: tuyển mộ, rời bang, thuế/chợ thật, skill thật, cường hoá tác động vào chiến đấu (mục 20).
### 18.2 Kết quả (lần chạy đầu, cần tinh chỉnh)
- Solo PA100 lên lv100: `kim_2` 4,2 ngày; `hoa_2`/`tho_1` 5,2; `moc_1` 6,1; `thuy_1` 7,5 (mong manh, 128 lần chết). Đội 5 người: PA40 3,8 ngày / PA100 71 giờ / PA160 57 giờ.
- Nhịp theo chuyển sinh: xem 4.3 (lv200 sau ~54 ngày AFK 24/7).
- Buffer nhanh hơn ≈16% (lv50: 37 giờ so với 43 giờ ở lần đo trước khi đổi nhịp).
- Raid: vách thắng/thua ở khoảng 80–90% level boss với 20 người (`raid_hp_mult=6`). Boss Hoàng Kim sớm hơi khó so với mặt bằng.
- Offline 24 giờ đội 5 người: `fast_forward` mặc định ≈ 0,5 giây so với 1,6 giây chạy chính xác (Python; cần đo lại trên thiết bị).
### 18.3 Kinh tế
Vàng vẫn lạm phát nếu chỉ có mua trang bị thường (đủ bộ trong 0,1–0,6 giờ thu nhập; ~5–6 triệu vàng/thành viên tới lv100). Giải pháp ở mục 19: tiêu hao thuốc/buff ≈ 23% thu nhập, cường hoá là hố sâu không đáy, phí duy trì bang, công trình ≈ 44 triệu vàng.

## 19. Hệ thống tiêu vàng [ĐỀ XUẤT — số liệu chỉnh bằng simulator]
Mục tiêu: người chơi luôn có thứ đáng tiêu vàng ở mọi giai đoạn, nhưng **không** ép mua bằng tiền thật (Linh Bảo không mua được bùa cường hoá, thuốc, buff).

### 19.1 Thu nhập tham chiếu
≈ `1000 × level` vàng/giờ/người (đo ở mục 5 của báo cáo; `income_ref_per_level`).

### 19.2 Tiêu hao thường xuyên (giá đã đặt trong `items.csv`)
| Loại | Công trình | Hiệu ứng | Giá | Dùng/giờ | % thu nhập |
|---|---|---|---|---|---|
| Thuốc máu `pot_hp_*` | Dược Phòng | hồi máu | `14·level_req` | 5 | 7% |
| Thuốc nội lực `pot_mp_*` | Dược Phòng | hồi nội lực | `11·level_req` | (theo phái) | — |
| Tiệc `feast_*` | Thiện Đường | +10% XP trong 1 giờ | `90·level_req` | 1 | 9% |
| Rượu `brew_*` | Tửu Quán | +10% sát thương trong 1 giờ | `70·level_req` | 1 | 7% |
| Đồ ăn `food_*` | Thiện Đường | no/tâm trạng | `6·level_req` | theo hệ thống no | nhỏ |
Tổng khi dùng đầy đủ ≈ **23% thu nhập**. Buff là tuỳ chọn (người chơi có thể bỏ để dư vàng cho thứ khác). AI "Utility" của thành viên tự mua theo ngưỡng vàng và tâm trạng.

### 19.3 Cường hoá trang bị (`bld_enhance`, `data/enhance.csv`)
- Chi phí mỗi lần thử = `enhance_base_per_level(30) × level_req của món × cost_mult`. Thất bại từ +6 trở lên **tụt 1 cấp**; không bao giờ mất món. `item_enhance_ward` (Bùa Hộ Cường, **chỉ chế tạo, không bán**) giữ nguyên cấp khi thất bại, dùng được từ +6.
- Cấp tối đa theo cấp công trình (`max_enhance_lv` 2→20).
| Mục tiêu | Giờ thu nhập/món (không bùa) | Có bùa | Chỉ số cộng |
|---|---|---|---|
| +5 | 0,3 | 1,3 | +20% |
| +8 | 1,4 | 3,0 | +32% |
| +10 | 6,1 | 6,0 | +40% |
| +12 | 37,7 | 13,0 | +45% |
| +15 | ~2.200 | 52,6 | +52% |
| +20 | không khả thi (~4×10^8 giờ) | 826 | +65% |
Ý đồ: đến +10 là mục tiêu thường; +11…+20 chỉ khả thi bằng bùa và là hố tiêu vàng cuối game (kéo dài sau chuyển sinh). Cảnh báo cân bằng: +10 cho +40% chỉ số, phải đưa vào mô phỏng chiến đấu (mục 20) trước khi chốt.

### 19.4 Bang
- **Thuế**: `guild_tax_pct = 10%` thu nhập thành viên chuyển vào quỹ bang (đổi được ở công trình/chính sách; thuế cao làm giảm `mood/loyalty`, xem 6.8).
- **Phí duy trì**: `guild_upkeep_per_level_day = 700 × level` vàng/người/ngày, trừ vào quỹ bang (≈3% thu nhập AFK 24/7); quỹ cạn → buff công trình tắt dần, không xoá dữ liệu.
- **Công trình**: tổng 44,2 triệu vàng + nguyên liệu để lên tối đa (≈ 11,5 ngày thuế 10% của 20 người lv70); thời gian xây thật theo `build_time_min`.
- **Chuyển sinh**: `gold_cost` 0 → 200k → 1M → 5M → 20M → Phi Thăng 50M (`rebirth.csv`) + Chuyển Sinh Đan.
- **Chế tạo**: công thức tốn vàng + nguyên liệu (giá bằng ~30% giá bán).

### 19.5 Chống lạm phát (kiểm tra bằng simulator)
Chỉ số theo dõi mỗi lần chạy: `gold_in/giờ`, `gold_out/giờ` theo level, tỉ lệ `out/in` mục tiêu 60–90% ở trạng thái ổn định; quỹ bang không tăng vô hạn; người chơi lv100 không dư >50 giờ thu nhập tiền mặt khi đã mua đủ đồ cần.


## 20. Kế hoạch mở rộng lõi mô phỏng (đã ghi lại, chưa làm) [CHỐT ghi nhận]
Lõi Python hiện có săn/party/raid/offline/nhịp XP. Các module dưới đây làm **theo thứ tự**, mỗi module có tiêu chí nghiệm thu để biết khi nào xong. Tất cả phải tất định (cùng seed → cùng kết quả), data-driven, có unit test, và cập nhật `balance_sim`.

| # | Module (file) | Nội dung | Tiêu chí nghiệm thu |
|---|---|---|---|
| S1 | `sim/recruit.py` | Sinh ứng viên: hệ, phái, level, PA (phân phối lệch, hiếm ở trên), 40 trait (xung đột, điều kiện lộ), tốc độ đến thụ động theo Tụ Nghĩa Đường + danh vọng, mời chủ động (Chiêu Hiền Lệnh), Thám Tử Quán cho PA gần đúng (sao/khoảng). Tăng tỉ lệ ứng viên `moc_1` khi đội thiếu buffer | Phân phối PA/trait khớp thiết kế (test thống kê, 10.000 mẫu); không ứng viên nào vi phạm xung đột trait; sai số ước lượng PA nằm trong khoảng đã nêu |
| S2 | `sim/retention.py` | `loyalty`, `mood` từ thuế, chia đồ, bị thương, ăn uống/nghỉ, trait, quan hệ; yêu cầu rời bang → điều kiện ở lại → đàm phán → kết cục (ở lại / bị thương dưỡng sức / rời); danh sách người tự do toàn cục cho bang NPC mời; quay lại theo cốt truyện | Mô phỏng 30 ngày: tỉ lệ rời bang nằm trong 3–10%/tháng với cấu hình chuẩn; không ai rời trong ngày đầu; thuế 10% không làm sập mood; có test cho từng nhánh đàm phán |
| S3 | `sim/economy_full.py` | Thuế → quỹ bang, phí duy trì, Chợ Bang (mua/bán, giá động nhẹ), đơn Thương Hội, hàng đợi xây công trình, chế tạo, tiêu hao thuốc/tiệc/rượu thực sự trong chiến đấu | `gold_in` và `gold_out` theo giờ (19.5) nằm trong 60–90% ở lv30/60/100; quỹ bang ổn định; test bảo toàn tiền (tổng vào = tổng ra + dư) |
| S4 | `sim/skills.py` | Đọc `skills.csv` thật (hiệu ứng theo `L`), phụ thuộc `prereq`, mana/cooldown, buff/heal/CC/DoT, tuyệt kỹ + bí kíp mở theo wave/chuyển sinh | Mỗi phái chạy được 1 trận đầy đủ; DPS/hiệu quả vai trò khớp `sim_roles` ±15%; phái buffer cải thiện đội đúng hệ số thiết kế |
| S5 | `sim/enhance.py` + tích hợp | Cường hoá thật vào chỉ số chiến đấu (`stat_pct_total`), bùa, giới hạn theo cấp công trình; chạy lại toàn bộ `balance_sim` và `calibrate` | Thời gian lên cấp lv100 không lệch >15% so với bản chưa có cường hoá khi người chơi cường hoá hợp lý (+5…+8); không xuất hiện combo vượt boss 1.5× level |
| S6 | `sim/rebirth.py` | Luồng chuyển sinh: điều kiện, Đan, giữ skill theo %, đổi phái miễn phí, phần thưởng, trần level; Phi Thăng/Trưởng Lão và buff toàn bang | Chu trình lv1→200 + Phi Thăng chạy hết không lỗi; thời gian từng giai đoạn khớp 4.3 ±20% |
| S7 | `sim/world.py` | Bang NPC cục bộ (Lôi Đài), Vô Tận Tháp vô hạn tầng, Boss Hoàng Kim mỗi 60 phút + boss tồn đọng khi offline, Triệu Tập Lệnh | Offline 24 giờ tạo đúng số boss tồn đọng (tối đa 3); Tháp tầng N có độ khó tăng tuyến tính/đa thức đã định |
| S8 | `sim/save.py` | Tuần tự hoá toàn bộ trạng thái (JSON), `schema_version` + migration theo wave, băm kiểm tra, mô phỏng xung đột cloud save (lấy bản mới nhất theo `updated_at`, báo khi lệch lớn) | Lưu → nạp → chạy tiếp cho kết quả y hệt chạy liên tục (test tất định); nạp save v1 từ file mẫu thành công sau migration |
| S9 | `tools/validate_balance.py` | Chạy bộ kịch bản chuẩn, so sánh với "ngân sách cân bằng" (bảng ngưỡng) và fail CI nếu vượt | Tích hợp lệnh một dòng, in bảng pass/fail |

**Việc chưa quyết cần lưu ý:** (1) skill thật và cường hoá chắc chắn làm lệch nhịp hiện tại, đo lại và chỉnh `xp_kill_coef`/`xp_rebirth_mult` sau S4–S5; (2) `thuy_1` solo mong manh (128 lần chết), xem xét buff cho phái này hoặc hạn chế đi solo; (3) boss Hoàng Kim sớm hơi khó.

## 21. Bộ prompt để tiến hành code
Cách dùng: mở dự án trong Claude Code (hoặc cuộc trò chuyện mới), giải nén gói `jx1_tycoon_package.zip` vào thư mục dự án, **dán Prompt 0 trước**, rồi dán từng prompt theo thứ tự. Mỗi prompt kết thúc bằng tiêu chí nghiệm thu; yêu cầu Claude chạy test và báo kết quả. Không bỏ qua bước kiểm tra dữ liệu.

### Prompt 0 — Ngữ cảnh chung (dán đầu mọi phiên)
```
Bạn là kỹ sư trưởng của dự án game pixel tycoon "JX1 Tycoon" (tên tạm; sẽ đổi). Đọc docs/JX1_Tycoon_GDD.md (v1.0), README.md, GODOT_PORT.md, CLAUDE.md.
Nguyên tắc bất biến:
1. Data-driven: mọi con số/nội dung nằm trong data/*.csv; ID bất biến; tên hiển thị ở i18n/*.csv (vi + en). Không hard-code nội dung trong code.
2. Simulation Core headless, tất định (PCG32 trong sim/rng.py, KHÔNG dùng random của engine), không chạm UI/engine API. Presentation chỉ đọc state và gửi lệnh.
3. Luôn chạy trước khi báo xong: `python3 -I tools/content_validator.py` (0 lỗi) và `python3 -m unittest discover -s tests` (toàn bộ qua). Thêm test cho mọi hành vi mới.
4. Không đoán khi thiếu thông tin: ghi câu hỏi vào GDD mục 15 và hỏi tôi. Không dùng tên/art/dữ liệu của Võ Lâm 1 hay Evil Hunter Tycoon.
5. Hiệu năng mobile: không cấp phát trong vòng lặp nóng, chiến đấu hướng sự kiện, offline dùng fast_forward (không chạy từng tick).
6. Mọi thay đổi bảng số phải chạy `python3 tools/balance_sim.py --quick` và nêu khác biệt.
Trả lời bằng tiếng Việt; code/comment/tên biến bằng tiếng Anh. Kết thúc mỗi việc bằng: đã làm gì, test nào qua, rủi ro, việc tiếp theo.
```

### Giai đoạn A — Mở rộng lõi Python (làm trước, không cần Godot)
**Prompt S1 — Tuyển mộ**
```
Làm module S1 trong GDD mục 20: sim/recruit.py. Đọc data/traits.csv, data/schools.csv, data/config.csv, GDD mục 5, 6.7.
Yêu cầu: sinh ứng viên tất định (nhận Rng), PA phân phối lệch (hiếm ở trên, 0–200), 0–3 trait theo xung đột/điều kiện lộ, tốc độ đến thụ động theo cấp bld_scout và danh vọng, mời chủ động bằng item_recruit_token, ước lượng PA hiển thị dạng sao/khoảng, tăng xác suất ứng viên moc_1 khi đội thiếu buffer (config recruit_buffer_boost). Thêm tham số vào data/config.csv và cập nhật validator nếu thêm cột.
Test: phân phối PA/trait (10.000 mẫu), không vi phạm xung đột, ước lượng PA chứa PA thật ≥ 90% trường hợp.
```
**Prompt S2 — Giữ chân / rời bang**
```
Làm S2: sim/retention.py theo GDD 6.8, 6.9 và mục 20. loyalty/mood từ thuế, chia đồ, thương tích, ăn uống/nghỉ, trait; yêu cầu rời bang → điều kiện ở lại → đàm phán → kết cục (ở lại / bị thương dưỡng sức / rời bang). Người rời vào danh sách người tự do toàn cục để bang NPC mời hoặc quay lại theo cốt truyện (chỉ cần hook sự kiện). Thêm đổi phái (Tàng Kinh Các) với chi phí và mất skill theo skill_keep_pct.
Test: mô phỏng 30 ngày, tỉ lệ rời bang 3–10%/tháng với cấu hình chuẩn, đủ test cho mỗi nhánh đàm phán, tất định.
```
**Prompt S3 — Kinh tế đầy đủ**
```
Làm S3: sim/economy_full.py theo GDD mục 6.6, 19. Thuế→quỹ bang, phí duy trì, Chợ Bang mua/bán, đơn Thương Hội, hàng đợi xây công trình (build_time_min), chế tạo từ recipes.csv, tiêu hao thuốc/tiệc/rượu thực trong chiến đấu (hp<50% dùng thuốc; buff trước chuyến săn). Thêm đo gold_in/gold_out theo giờ vào balance_sim.
Nghiệm thu: out/in trong 60–90% ở lv30/60/100; test bảo toàn tiền; quỹ bang không tăng vô hạn.
```
**Prompt S4 — Skill thật**
```
Làm S4: sim/skills.py đọc data/skills.csv (effects dùng biến L, prereq dạng id:cấp). Thực thi mana/cooldown, buff/heal/CC/DoT, tuyệt kỹ và bí kíp theo unlock_wave. Thay hệ số skill_dps_bonus bằng skill thật; chạy calibrate.py để chỉnh lại monster_dmg_factor và xp_kill_coef sao cho mốc thời gian ở GDD 4.3 lệch ≤15%. Báo cáo DPS theo vai trò so với sim_roles.csv.
```
**Prompt S5 — Cường hoá tích hợp**
```
Làm S5: sim/enhance.py. Dùng data/enhance.csv, Bùa Hộ Cường, giới hạn theo max_enhance_lv của bld_enhance. Gắn stat_pct_total vào Member.stats(). Chính sách người chơi giả lập: cường hoá tới +5…+8 khi vàng dư. Chạy lại balance_sim/calibrate và nêu thay đổi nhịp; đề xuất chỉnh enhance.csv nếu cường hoá làm thời gian lên lv100 lệch >15% hoặc cho phép thắng boss ≥1.5× level.
```
**Prompt S6–S9** (mỗi cái theo bảng mục 20)
```
Làm lần lượt S6 (rebirth), S7 (world: bang NPC, Tháp, boss Hoàng Kim + tồn đọng offline), S8 (save + migration + test tất định "lưu-nạp-chạy tiếp"), S9 (validate_balance.py với ngân sách cân bằng và fail khi vượt). Mỗi module xong phải chạy validator, unit test, balance_sim --quick; cập nhật GDD mục 18 với kết quả đo.
```

### Giai đoạn B — Godot (song song từ khi có máy thật)
**Prompt P1 — Spike kỹ thuật (GDD 12.1)**
```
Tạo dự án Godot 4.x (GDScript) tối giản để kiểm chứng trên máy Android thật: (1) vẽ 200 sprite placeholder di chuyển ở 60 FPS và đo nhiệt/pin 10 phút; (2) AdMob banner + rewarded; (3) IAP non-consumable "premium"; (4) Google Sign-In; (5) gọi REST Supabase lưu/đọc một save; (6) chạy thử llama.cpp model nhỏ ở chế độ tải thêm. Với mỗi mục: kết quả, số đo, rủi ro. Nếu ≥3 mục thất bại, đề xuất chuyển Unity kèm lý do. KHÔNG làm iOS (chưa có Apple Developer).
```
**Prompt P2 — Port lõi sang GDScript**
```
Theo GODOT_PORT.md, port sim/ sang GDScript trong res://core/: rng (PCG32 phải khớp golden vectors trong GODOT_PORT.md), data loader (đọc CSV), formulas, model, hunt, offline (fast_forward), raid. Viết test (GUT hoặc script riêng) chạy headless `godot --headless` so khớp với đầu ra Python cho 5 seed (kết quả sai lệch cho phép = 0 với RNG, ≤1e-9 với số thực). Đo thời gian offline 24h đội 5 người trên Android thật; nếu >1 giây, tối ưu hoặc đề xuất GDExtension.
```
**Prompt P3 — Vertical slice (GĐ 1)**
```
Làm lát cắt chơi được 30–60 phút theo GDD 12.2 GĐ1: map realtime (placeholder bằng code theo hệ/phái), 3 phái, 1 bãi, 1 boss, 5 công trình (Tổng Đàn, Thiện Đường, Dược Phòng, Chợ Bang, Luyện Khí Đài), save/load. UI chỉ đọc state từ core, gửi lệnh qua một lớp Command. Màn hình: bang, danh sách thành viên (CA/ước lượng PA), bản đồ săn, công trình, cài đặt (vi/en).
```
**Prompt P4 — Core loop (GĐ 2) và Wave 1 (GĐ 3)**
```
Tích hợp các module S1–S6 vào Godot: tuyển mộ, CA/PA/trait, giữ chân/rời bang, Chợ Bang/thuế/cường hoá, offline progress (cap 8h Free/24h Premium), nhiệm vụ ngày/tuần (ad_variant/premium_auto_claim), chuyển sinh 1, Boss Hoàng Kim và raid cả bang (giới hạn số sprite vẽ theo GDD 6.13). Nội dung Wave 1 = cờ wave=1; các wave sau khoá bằng content_wave.
```
**Prompt P5 — Services (GĐ 4)**
```
Làm lớp Services theo GDD mục 8, 11: Supabase (Auth, cloud save, bảng xếp hạng bang/thành viên, kho Thiên Cơ Kính/Nhãn trong cloud), AdMob banner (chỉ Free) và rewarded cho nhiệm vụ quảng cáo, IAP Premium (non-consumable, khôi phục mua) và Kính/Nhãn (Kính là consumable → lưu số dư trên cloud), FeatureFlags theo entitlement. Premium không bao giờ thấy quảng cáo; nhiệm vụ quảng cáo không bao giờ thưởng Kính/Nhãn.
```
**Prompt P6 — AI + bản địa hoá + art pipeline (GĐ 5)**
```
(1) Utility AI luôn bật cho thành viên (chọn bãi, mua đồ, nghỉ, xin rời). (2) LLM local tuỳ chọn (gói tải thêm, template khung chặt, fallback template khi tắt), có nút báo cáo nội dung trong app (chính sách Google Play cho nội dung AI). (3) i18n vi/en cho toàn bộ UI. (4) Công cụ art: script hạ độ phân giải, quantize về palette chung, snap lưới pixel, cắt/ghép sprite sheet, ghép paper-doll và palette swap theo hệ; sinh placeholder art; tạo ART_LICENSE_LOG.md (công cụ, gói, ngày, prompt, file) và hướng dẫn Stable Diffusion cục bộ + LoRA pixel-art (kiểm tra license từng model).
```
**Prompt P7 — Phát hành Android (GĐ 6)**
```
Chuẩn bị release Android: tối ưu kích thước (nén texture, bỏ tài nguyên thừa, tách gói LLM), kiểm thử thiết bị thật (nhiệt, pin, FPS), checklist Play Console (Data safety, chính sách quảng cáo, nội dung AI, xếp hạng độ tuổi), kiểm tra bản quyền tên (nhãn hiệu) và truyền thuyết (tra nguồn). Xuất bản nội bộ → kín → mở.
```

### Việc cần làm tay (Claude không làm thay)
- Tra điều khoản gốc của công cụ art, lưu bằng chứng; tra nhãn hiệu tên phái/vùng; xác minh chi tiết truyền thuyết.
- Tài khoản: Google Play Console (đã có), AdMob, Supabase, về sau Apple Developer.
- Chơi thử vertical slice để duyệt nhịp chơi và độ khó.
