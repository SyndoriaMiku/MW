# Maple World Frontend — Roadmap

Cập nhật: 2026-10-01. Đánh dấu `[x]` khi xong từng mục.

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

- [ ] Màn đăng ký (`users/register/`)
- [ ] Màn tạo nhân vật khi `characters/my/` báo chưa có nhân vật (chọn class từ `classes/`)
- [ ] Dùng `session/bootstrap/` để launcher tải dữ liệu một lần thay vì gọi tuần tự

## Giai đoạn 3 — Battle hoàn chỉnh

- [ ] Hiển thị nhiều quái (backend có `stage_enemies`, client chỉ vẽ `first_enemy`) + chọn mục tiêu
- [ ] Màn kết quả: EXP, level up, drop, tiền
- [ ] Nút bỏ trận (`battles/<id>/forfeit/`)
- [ ] Dùng item trong trận (`action_type: ITEM`)
- [ ] Gửi `expected_version` để tránh xung đột trạng thái
- [ ] Xử lý `skip-idle-turn` / phase quái rõ ràng; `_status_text` hiện đúng phase
- [ ] Nút "Retry" ở chế độ live đổi thành "Về sảnh"/"Vào lại dungeon"
- [ ] Sprite nhân vật/quái, animation đánh, số damage bay lên

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
