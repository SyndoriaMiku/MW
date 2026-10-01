# Maple World Frontend — Roadmap

Cập nhật: 2026-09-30. Đánh dấu `[x]` khi xong từng mục.

## Giai đoạn 0 — Dọn nền (nhỏ, làm ngay)

- [ ] `git init` + commit đầu tiên (hiện project chưa có version control)
- [ ] Xoá `src/assets/items/weapons/` (trùng với `assets/items/icons/`, không file nào dùng)
- [ ] Xoá hàm chết `_equipment_tooltip` trong `character_profile.gd`
- [ ] Sửa README: bản Godot thực tế (project đang khai báo 4.7), bỏ mô tả "1 vs 1" cũ, thêm cách chạy test
- [ ] Đưa `base_url` ra cấu hình (ProjectSettings hoặc file `.cfg`), label server ở màn login đọc từ đó
- [ ] Mock battle: nhánh skill chưa xử lý người chơi bị hạ (thiếu `battle_defeat`)

## Giai đoạn 1 — Hạ tầng dùng chung

- [ ] `ItemIconRegistry` (autoload): gom preload icon + đọc `item_icon_catalog.json` — hiện đang lặp ở 3 màn (character, inventory, enhancement)
- [ ] `SceneRouter`: gom hằng số đường dẫn scene + điều hướng
- [ ] ApiClient: thêm `unwrap_list()`, signal `unauthorized` → router tự về login (bỏ `_accept_response` lặp ở mọi màn)
- [ ] Refresh token: khi 401 thì gọi `users/token/refresh/` rồi retry 1 lần; chỉ về login nếu refresh thất bại
- [ ] Logout gọi `users/logout/` để blacklist refresh token
- [ ] (Tuỳ chọn) Lưu refresh token xuống `user://` để khỏi đăng nhập lại mỗi lần mở game
- [ ] Theme `.tres` dùng chung thay cho StyleBoxFlat tạo tay trong code/tscn

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
- [ ] Khôi phục Aurora roll đang chờ khi quay lại màn Enhancement (hiện chỉ giữ trong RAM)
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

- [ ] Test runner headless chạy toàn bộ `tests/` bằng 1 lệnh (hoặc dùng GUT) + CI
- [ ] Âm thanh, hiệu ứng chuyển cảnh
- [ ] Đa ngôn ngữ (VI/EN) qua `TranslationServer`
- [ ] Preset export (Windows/Web) + build script
