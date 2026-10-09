# Maple World Frontend — Roadmap

Cập nhật: 2026-10-03. Đánh dấu `[x]` khi xong từng mục.

## Giai đoạn 0 — Dọn nền ✅

- [x] Đưa project lên git
- [x] Chuyển ảnh gốc 1254px từ `src/assets/items/weapons/` sang `assets/items/source/` (có `.gdignore`)
- [x] Xoá hàm chết `_equipment_tooltip` trong `character_profile.gd`
- [x] Sửa README: Godot 4.7, tính năng hiện có, cấu trúc thư mục, cách chạy test
- [x] `base_url` lấy từ project setting `maple_world/network/api_base_url`, ghi đè được bằng `-- --api-url=...`; màn login hiện đúng server
- [x] Mock battle: dùng skill rồi bị hạ giờ kết thúc trận (`battle_defeat`)

## Giai đoạn 1 — Hạ tầng dùng chung ✅

- [x] `ItemIcons` + `ItemTypes` (`src/shared/items/`): một nơi duy nhất cho icon và danh sách loại trang bị; bỏ `item_icon_catalog.json`
- [x] `SceneRouter` (autoload): hằng số scene, điều hướng, `require_session()`
- [x] ApiClient: `unwrap_list()`, `error_message()`, signal `session_expired` → router tự về login
- [x] Refresh token: 401 → refresh một lần (không refresh trùng khi nhiều request cùng lỗi) → retry
- [x] Logout gọi `users/logout/` để blacklist refresh token
- [x] Request có timeout 15 giây
- [x] Theme `main_theme.tres` cho toàn project; scene dùng biến thể `PrimaryButton`, `CompactPanel`, `HPBar`, `MPBar`, `EnemyHPBar`, `EXPBar`
- [x] `tools/run_tests.sh` chạy toàn bộ test; thêm `check_api_client` (server HTTP giả kiểm tra refresh/logout)
- [x] `GameCache`: cache GET dùng chung cho mọi màn — dữ liệu tham chiếu 6 giờ (lưu đĩa với server thật), dữ liệu người chơi 5 phút và tự xoá khi có POST liên quan; gộp request trùng; header Hub tự cập nhật khi dữ liệu đổi
- [ ] (Tuỳ chọn) Lưu refresh token xuống `user://` để khỏi đăng nhập lại mỗi lần mở game
- [x] Theme Material 3 Expressive, bảng màu sáng từ màu gốc `#336DFF`: màu theo role trong `M3`, theme sinh từ `tools/build_theme.gd`, font Roboto + icon Material Symbols Rounded, ripple + thu nhỏ khi bấm cho mọi nút
- [x] Bỏ màu hardcode trong scene/script — StyleBox còn tạo trong code đều lấy màu từ `M3`
- [ ] Đổi chữ IN HOA trên các nút cũ sang sentence case theo M3

## Giai đoạn 2 — Onboarding đầy đủ

- [x] Màn đăng ký (`users/register/`): kiểm tra form ở client, lỗi server hiện dưới từng ô, đăng ký xong vào thẳng màn tạo nhân vật
- [x] Màn tạo nhân vật: chọn job (class suy ra từ job), xem chỉ số và skill của job, luật tên giống backend (`CharacterNameRules`); launcher tự chuyển tới đây khi `characters/my/` trả 404
- [x] Màn Hub thay launcher: header (avatar, tên, Lumis/Nova, thanh stamina hồi theo thời gian thực), ô nội dung, thanh điều hướng 7 mục; Back (Esc / nút back chuột) chạy ngược hiệu ứng chuyển trang
- [x] Hub tải một lần bằng `session/bootstrap/` (có fallback cho server cũ)
- [x] Home: ảnh nền (vẽ tạm, thay bằng `assets/ui/home_background.png`), sự kiện rate đang chạy, nút Adventure / Resume battle
- [x] Adventure: danh sách dungeon theo thứ tự kéo thả trong Studio (`order`), khoá theo level / stamina / trận đang dở, kèm lý do
- [ ] Ảnh nền thật cho Home và ảnh đại diện theo job

Sửa kèm khi làm Giai đoạn 2:

- [x] ID số từ JSON là float (`5` → `"5.0"`), làm URL `inventory/5.0/equip/` trả 404 — nút Equip/Unequip trước đây hỏng với backend thật. Dùng `ApiClient.id_string()` cho mọi ID
- [x] `ApiClient` đọc định dạng lỗi chung của backend (`code`, `message`, `fields`)

## Giai đoạn 3 — Battle hoàn chỉnh ✅

- [x] Đọc đúng event của backend (`action`, `effect_tick`, `turn_skipped`, `forfeit`, `battle_result`) — trước đây client chờ các khoá `type` mà server không bao giờ gửi
- [x] Hiển thị nhiều quái + click để chọn mục tiêu; skill đánh lan / tự thân không cần mục tiêu
- [x] Nhận diện nhân vật của mình qua `entity_id` (đúng cho trận party)
- [x] Màn kết quả: EXP, Lumis, level up, item rơi; thua thì báo không mất stamina
- [x] Nút Forfeit (có hộp xác nhận)
- [x] Dùng item trong trận (`action_type: ITEM`), hiện số lượng và cooldown
- [x] Gửi `expected_version` (409 → tự tải lại) và `client_action_id` (lỗi mạng → gửi lại an toàn)
- [x] Trận party: poll khi chờ người khác, nút bỏ lượt người chơi treo máy (`skip-idle-turn`), hiện đúng phase
- [x] "Enter again" vào lại cùng dungeon, "Back to board" khi trận kết thúc
- [x] Số damage/heal bay lên, thanh máu tụt theo từng event, thẻ nháy khi trúng đòn
- [x] Mock offline trả dữ liệu đúng định dạng backend (2 quái, skill đánh lan, bình máu, phần thưởng)
- [ ] Sprite nhân vật/quái và animation đánh thật (cần art; hiện dùng ô màu thay thế, `visual_key` đã có sẵn trong dữ liệu)
- [ ] Hiển thị biểu tượng hiệu ứng (buff/debuff) thay vì chỉ ghi tên

## Giai đoạn 4 — Kinh tế & phát triển nhân vật

- [x] Shop: mua theo danh mục (Lumis/Nova), double-click để mua, nhập số lượng cho item stack, giới hạn mua theo chu kỳ
- [x] Bán item từ túi (hỏi xác nhận, nhập số lượng nếu là chồng) và **buy back** 10 lần bán gần nhất (backend: model `SoldItem`, `inventory/buyback/`), giữ nguyên Lumen/Aurora
- [x] Tải đủ mọi trang của danh sách (`ApiClient.get_all`) — trước đây túi đồ quá 20 món bị thiếu
- [x] Inventory: double-click để equip/unequip (vào ô trống, hoặc thay ô đang so sánh), dùng bùa buff, mở Enhancement tab Aurora với essence đã chọn
- [x] Tooltip khi hover: mô tả item; trang bị so sánh với món cùng ô kèm chênh lệch chỉ số; middle-click đổi ô so sánh với Ring/Pendant
- [x] Lấy số slot từ `inventory/slots/` thay cho hardcode ring=4 / pendant=2
- [x] Hộp chọn Aurora bắt buộc: roll đang chờ được lấy từ server (`pending_aurora_roll` trong inventory API) và mở lại mỗi khi vào Enhancement; so sánh dòng cũ/mới, chọn dòng cho triple choice
- [x] Roll có tăng cấp Aurora phải lấy dòng mới (backend từ chối `keep_old`)
- [x] Nhận diện Essence theo field backend (`use_kind`) thay vì tên chứa chữ "essence"
- [x] Trang Skills: skill đã học (sát thương hiện tại và cấp sau, MP, hồi chiêu, mục tiêu), skill sắp mở khoá theo level, nâng cấp bằng vật liệu (hiện số đang có / cần); cấp tự động thì ghi rõ
- [ ] Special shop (đổi vật liệu lấy item, `shops/special/`), lịch sử Nova (`users/nova/history/`)

## Giai đoạn 5 — Nội dung & xã hội

- [x] Trang Quests: lọc daily/weekly/story, tiến độ từng mục tiêu, phần thưởng, nhận thưởng; badge trên thanh điều hướng và thẻ trên Home đếm quest chờ nhận
- [x] Boss dungeon: kỳ reset, số người tối đa, chỉ trưởng nhóm vào; chưa có party thì tạo party 1 người rồi vào
- [x] Bản đồ thế giới: chip region → location → dungeon (`world/regions/`), dungeon không có location vào mục "Elsewhere"
- [ ] Party (tạo, mời, loot)
- [ ] Market / trade

## Giai đoạn 6 — Chất lượng & phát hành

- [x] Test runner headless chạy toàn bộ `tests/` bằng 1 lệnh (`tools/run_tests.sh`)
- [ ] CI chạy test tự động
- [x] Settings: chế độ cửa sổ (windowed / borderless fullscreen), độ phân giải, âm lượng BGM và SFX
- [ ] Nhạc nền và hiệu ứng âm thanh (bus `BGM`/`SFX` đã sẵn sàng), hiệu ứng chuyển cảnh
- [ ] Đa ngôn ngữ (VI/EN) qua `TranslationServer`
- [ ] Preset export (Windows/Web) + build script
