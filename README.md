# Audio Card Cutter (AnkiVN)

Add-on Anki cắt file audio dài và tự tạo thẻ mới với đoạn audio đã cắt.
Toàn bộ giao diện viết bằng PyQt — không có WebView, không HTML/JS.

## ✨ Tính năng

- Chọn file audio (MP3, WAV, M4A, OGG, FLAC, AAC, OPUS).
- Phát thử + thanh tua + hiển thị thời gian.
- Đánh dấu vùng cắt bằng nút **vị trí hiện tại** hoặc gõ tay (mm:ss.ms).
- Nút **Preview** phát đúng đoạn đã chọn để kiểm tra trước khi cắt.
- Cắt bằng `ffmpeg`, lưu thẳng vào `collection.media`.
- Tự thêm thẻ với deck/notetype tuỳ chọn, điền nội dung text + tag tại chỗ.
- Cửa sổ giữ nguyên trạng thái sau khi thêm thẻ — cắt liên tục cực nhanh.

## 🧰 Yêu cầu

- Anki 2.1.50+ (Qt5 hoặc Qt6).
- **FFmpeg** trong PATH (hoặc cấu hình `ffmpeg_path`).
  - Windows: `winget install ffmpeg` hoặc `choco install ffmpeg`.
  - macOS: `brew install ffmpeg`.
  - Linux: cài qua package manager.

## 🚀 Sử dụng

1. Menu **AnkiVN → Audio Card Cutter** (hoặc `Ctrl+Shift+A`).
2. **Chọn file audio…** → chọn file lớn.
3. Nhấn **▶** để phát; tới chỗ cần cắt nhấn `[` (set start), tới chỗ kết thúc nhấn `]`
   (set end). Hoặc nhập tay vào ô Bắt đầu / Kết thúc.
4. Nhấn **🔁 Preview** (`P`) để nghe lại đoạn vừa đánh dấu.
5. Chọn deck, notetype, điền các trường text + tag.
6. **✂ Cắt && Thêm thẻ** (`Ctrl+Enter`). Lặp lại bước 3–6 để cắt tiếp.

## ⌨️ Phím tắt

| Phím             | Tác dụng                          |
| ---------------- | --------------------------------- |
| `Space`          | Phát / Tạm dừng                   |
| `[`              | Đặt thời điểm bắt đầu             |
| `]`              | Đặt thời điểm kết thúc            |
| `P`              | Preview vùng đã chọn              |
| `Ctrl + Enter`   | Cắt và thêm thẻ                   |
| `Ctrl + W`       | Đóng cửa sổ                       |

## ⚙️ Config (Tools → Add-ons → Config)

| Key                | Ý nghĩa                                                |
| ------------------ | ------------------------------------------------------ |
| `audio_field`      | Tên field chứa `[sound:...]`. Mặc định `Audio`.        |
| `default_deck`     | Deck mặc định khi tạo thẻ. Trống = deck hiện tại.       |
| `default_notetype` | Note type mặc định. Trống = notetype hiện tại.         |
| `output_format`    | `mp3`, `ogg`, `wav`, `m4a`. Mặc định `mp3`.            |
| `output_bitrate`   | Bitrate audio. Mặc định `128k`.                        |
| `ffmpeg_path`      | Đường dẫn ffmpeg nếu không có trong PATH.              |
