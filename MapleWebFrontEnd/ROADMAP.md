# Maple World Frontend — Roadmap

Cập nhật: 2026-10-01 (chiều). Đánh dấu `[x]` khi xong từng mục.

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
- [ ] (Tuỳ chọn) Lưu refresh token xuống `user://` để khỏi đăng nhập lại mỗi lần mở game
- [ ] StyleBoxFlat còn tạo trong code (ô trang bị, thẻ item, popup skill, tooltip) — chuyển sang theme khi làm lại các màn đó

## Giai đoạn 2 — Onboarding đầy đủ

- [x] Màn đăng ký (`users/register/`): kiểm tra form ở client, lỗi server hiện dưới từng ô, đăng ký xong vào thẳng màn tạo nhân vật
- [x] Màn tạo nhân vật: chọn job (class suy ra từ job), xem chỉ số và skill của job, luật tên giống backend (`CharacterNameRules`); launcher tự chuyển tới đây khi `characters/my/` trả 404
- [ ] Dùng `session/bootstrap/` để launcher tải dữ liệu một lần thay vì gọi tuần tự

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

- [ ] Inventory: bán (`sell`), dùng (`use`) item
- [ ] Lấy số slot từ `inventory/slots/` thay cho hardcode ring=4 / pendant=2
- [ ] Khôi phục Aurora roll đang chờ khi quay lại màn Enhancement (hiện chỉ giữ trong RAM; backend lưu ở model `PendingAuroraRoll`)
- [ ] Nhận diện Essence theo field backend thay vì tên chứa chữ "essence"
- [ ] Học / nâng cấp skill (`skills/learnable/`, `characters/my/skills/<id>/upgrade/`)
- [ ] Shop (`shops/`), lịch sử Nova (`users/nova/history/`)

## Giai đoạn 5 — Nội dung & xã hội

- [ ] Quest (`quests/`, claim thưởng)
- [ ] Boss dungeon (`world/boss-dungeons/`)
- [ ] Bản đồ thế giới theo region/location
- [ ] Party (tạo, mời, loot)
- [ ] Market / trade

## Giai đoạn 6 — Chất lượng & phát hành

- [x] Test runner headless chạy toàn bộ `tests/` bằng 1 lệnh (`tools/run_tests.sh`)
- [ ] CI chạy test tự động
- [ ] Âm thanh, hiệu ứng chuyển cảnh
- [ ] Đa ngôn ngữ (VI/EN) qua `TranslationServer`
- [ ] Preset export (Windows/Web) + build script
