# Audio Card Cutter (AnkiVN)

Add-on Anki cắt file audio dài và tự tạo thẻ mới với đoạn audio đã cắt.
Toàn bộ giao diện viết bằng PyQt — không có WebView, không HTML/JS. Phiên bản mới đã được nâng cấp mạnh mẽ về mặt trải nghiệm người dùng với **thanh hiển thị sóng âm (Waveform)** trực quan tương tự Audacity.

---

## ✨ Tính năng nổi bật

- **Trích xuất sóng âm trực quan (Interactive Waveform)**: Tự động vẽ phổ âm thanh dạng cột ngay khi nạp file. Hoạt động bất đồng bộ ở chế độ nền, không gây đứng hay đơ giao diện (kể cả với file dài hàng tiếng).
- **Chọn vùng thông minh (Audacity-like Region Selection)**: 
  - Click chuột trái để di chuyển Playhead (tới vị trí phát nhạc).
  - Giữ và kéo chuột trái để chọn (bôi đen) vùng âm thanh cần cắt.
- **Tính năng phát bổ sung**:
  - Tự động phát thử đoạn cắt (**Preview**) chỉ phát đúng vùng được chọn.
  - Hỗ trợ tùy chỉnh tốc độ phát (**Playback Speed**) từ 0.5x đến 2.0x.
  - Thiết lập độ lệch phản xạ (**Reaction time offset**) để bù đắp thời gian nhấn nút.
  - Tự động phát lại khi dịch chuyển điểm bắt đầu/kết thúc (**Auto hear on nudge**).
- **Thiết kế mô-đun (Clean Code)**: Cấu trúc code tuân thủ nguyên tắc Single Responsibility Principle (SRP) giúp dễ dàng phát triển và bảo trì.
- **Hệ thống Hoàn tác (Native Undo)**: Tích hợp chặt chẽ với hệ thống undo của Anki (`Ctrl+Z`), đảm bảo không lỗi cơ sở dữ liệu khi xóa thẻ đã tạo.
- **Nạp và xử lý đa định dạng**: MP3, WAV, M4A, OGG, FLAC, AAC, OPUS, WMV, v.v. thông qua bộ công cụ FFmpeg tích hợp.

---

## 🧰 Yêu cầu hệ thống

- Anki 2.1.50+ / Anki 23.12+ / Anki 24+ / Anki 25+ (Qt5 hoặc Qt6).
- **FFmpeg & FFprobe**:
  - Hệ thống hỗ trợ tự động tải xuống và cài đặt bộ nhị phân FFmpeg/FFprobe ngay trong giao diện (dành cho Windows).
  - Hoặc bạn có thể cài đặt thủ công qua hệ thống:
    - Windows: `winget install ffmpeg` hoặc `choco install ffmpeg`.
    - macOS: `brew install ffmpeg`.
    - Linux: Cài qua Package Manager của hệ điều hành.

---

## 🚀 Cách sử dụng

1. Vào menu **AnkiVN → Audio Card Cutter** (hoặc nhấn tổ hợp phím `Ctrl+Shift+A`).
2. Chọn **Chọn file audio…** và mở file của bạn. Giao diện sóng âm sẽ tự động tải ở phía dưới.
3. **Chọn vùng cần cắt**:
   - Nhấp chuột lên biểu đồ sóng để tua nhạc.
   - **Kéo chuột** bôi màu xanh đoạn bạn muốn lấy.
   - Sử dụng phím `[` và `]` hoặc các nút **Bắt đầu** / **Kết thúc** để tinh chỉnh chuẩn xác từng phần mười giây.
4. Nhấn phím **P** (Preview) để nghe thử đoạn cắt.
5. Chọn Deck, Notetype, nhập nội dung Text và Tag.
6. Nhấn **Ctrl+Enter** để thực hiện cắt và tạo thẻ. Cửa sổ nhập liệu sẽ giữ nguyên để bạn tiếp tục cắt các phần tiếp theo cực nhanh!

---

## ⌨️ Các phím tắt tiện ích

| Phím tắt | Tác dụng |
| :--- | :--- |
| `Space` | Phát / Tạm dừng |
| `[` | Đặt thời điểm Bắt đầu |
| `]` | Đặt thời điểm Kết thúc |
| `P` | Phát thử vùng đã chọn (Preview) |
| `Ctrl + Enter` | Thực hiện Cắt & Tạo thẻ |
| `Ctrl + W` / `Esc` | Đóng cửa sổ |
| `Ctrl + Z` (ở màn hình chính) | Hoàn tác thẻ vừa tạo (nếu lỡ tay) |

---

## 📂 Cấu trúc mã nguồn (Architecture)

Chi tiết cấu trúc mô-đun được mô tả trong [ARCHITECTURE.md](file:///c:/Users/ADMIN/AppData/Roaming/Anki2/addons21/audio_cutter/ARCHITECTURE.md):
- `ui.py`: Giao diện Dialog chính và Widget vẽ sóng âm `AudioWaveformWidget`.
- `player.py`: Lớp tương thích phát âm thanh Qt5/Qt6.
- `ffmpeg_utils.py`: Bộ điều phối và chạy FFmpeg/FFprobe nền để cắt & nạp sóng âm.
- `anki_interop.py`: Kết nối cơ sở dữ liệu Anki, tạo note và đồng bộ Undo.
- `constants.py`: Quản lý các cấu hình mặc định và giao diện hiển thị.
- `_tr.py`: Đa ngôn ngữ (English / Tiếng Việt).
