# Quick Translator (Rofi + Groq Cloud / Google Gemini Hybrid trên Fedora Linux / Wayland KDE Plasma)

Tài liệu này lưu trữ toàn bộ kiến trúc, cơ chế bảo mật, nguyên nhân lỗi và giải pháp kỹ thuật đã xử lý để các session sau có thể kế thừa và bảo trì ngay lập tức.

---

## 1. Môi trường & Luồng hoạt động (Architecture & Workflow)

- **Hệ điều hành:** Fedora Linux
- **Môi trường hiển thị:** Wayland (Compositor: KDE Plasma 6 / KWin)
- **Công cụ giao diện:** Rofi (phiên bản `2.0.0` hỗ trợ Wayland layer-shell / XCB)
- **Backend AI (Kiến trúc Hybrid):**
  - **Ưu tiên 1 (Primary):** Groq Cloud API (mặc định model `openai/gpt-oss-120b` hoặc `qwen/qwen3.8-27b`) cho tốc độ phản hồi siêu nhanh (~0.6s - 1.5s).
  - **Ưu tiên 2 (Fallback):** Google Gemini API (`gemini-3.5-flash-lite`) tự động kích hoạt làm phương án dự phòng khi Groq thiếu key, lỗi mạng hoặc chạm giới hạn.
- **Xử lý JSON & HTTP:** `curl` (với cờ `-4` IPv4) và `jq`.
- **Quản lý Clipboard:** `wl-copy` (Wayland native) và `xclip` (X11 fallback).
- **Quản lý Cấu hình & Bảo mật:**
  - Thứ tự nạp: `~/.config/rofi-translate/config.env` -> `$SCRIPT_DIR/config.env` -> `$SCRIPT_DIR/.env`.
  - Phân quyền nghiêm ngặt `chmod 600` (chỉ user sở hữu có quyền đọc/ghi).
  - Khóa toàn bộ các file credentials (`*.env`, `config.env`, `*.key`) trong `.gitignore` để không bao giờ bị lưu vào Git.

### Luồng xử lý chi tiết (Workflow):

1. **Bước 1 (Input Stage):**
   - Mở Rofi dạng thanh capsule nổi 600px căn giữa màn hình (`window { location: center; anchor: center; width: 600px; }`).
   - Nền tối mờ Glassmorphism (`rgba(28, 28, 30, 0.95)`), placeholder `"Type your words..."`.
   - **Tương tác nền:** Cửa sổ không chiếm toàn màn hình, người dùng vẫn nhìn thấy và tương tác bình thường với các cửa sổ ứng dụng phía sau. Thoát nhanh bằng phím <kbd>Escape</kbd>.
2. **Bước 2 (Loading Stage):**
   - Thay thế ô nhập bằng hộp thoại `Analyzing...` (chữ tím `#818cf8`, căn lề trái) với kích thước và vị trí trùng khớp 100% (600px).
   - Tạo cảm giác chuyển đổi mượt mà tại chỗ (seamless continuity), loại bỏ hoàn toàn hiện tượng co giật layout.
3. **Bước 3 (Hybrid API Request):**
   - Đóng gói input theo cấu trúc `SYSTEM_PROMPT` phân nhánh ngôn ngữ (Anh ↔ Việt) và ngữ cảnh (Từ vựng vs Câu).
   - Gọi **Groq API** trước. Nếu thành công, lấy bản dịch ngay tức thì.
   - Nếu Groq thất bại hoặc chưa cấu hình key, tự động chuyển tiếp sang **Gemini API**.
4. **Bước 4 (Response Stage):**
   - Tắt tiến trình Loading.
   - Hiển thị card kết quả nổi 760px ở giữa màn hình trên nền phủ mờ toàn bộ (`fullscreen: true; background-color: rgba(10, 10, 10, 0.45);`).
   - Tự động sao chép kết quả vào clipboard trong nền (`wl-copy`).
   - **Đóng cửa sổ linh hoạt:** Nhấn <kbd>Enter</kbd>, <kbd>Esc</kbd> hoặc **click chuột vào bất kỳ vùng nào bên ngoài card kết quả**.

---

## 2. Các vấn đề kỹ thuật cốt lõi và giải pháp (Knowledge Base)

### 📌 Vấn đề 1: Trải nghiệm tương tác chuột khác biệt giữa Input, Loading và Response trên Wayland
- **Triệu chứng & Thách thức:**
  - Trên Wayland, cơ chế bảo mật cô lập từng surface. Cửa sổ con không thể nhận click chuột nếu click nằm ngoài diện tích của nó.
  - Người dùng muốn: Trong khâu **Input** và **Loading**, người dùng vẫn tương tác được với không gian phía sau; nhưng ở khâu **Response**, click chuột ra ngoài box phải đóng ngay cửa sổ.
- **Giải pháp:**
  - **Khâu Input & Loading:** Dùng cửa sổ nổi 600px, không bật `fullscreen`. Người dùng thoải mái click chuột vào các ứng dụng bên dưới; chỉ hủy khi nhấn <kbd>Escape</kbd>.
  - **Khâu Response:** Bật `fullscreen: true` với lớp nền mờ `rgba(10, 10, 10, 0.45)` bao phủ 100% màn hình, kết hợp các cờ:
    ```bash
    ROFI_MOUSE_FLAGS=(
      -hover-select
      -me-select-entry ''
      -me-accept-entry '!MousePrimary'
      -kb-cancel 'Escape,MousePrimary'
    )
    ```
    Khi click chuột vào lớp nền mờ bên ngoài card, Rofi bắt được `MousePrimary` và hủy (`kb-cancel`) ngay lập tức.

---

### 📌 Vấn đề 2: Lỗi hộp thoại Loading và hiển thị lỗi bị văng chữ lên góc màn hình (`rofi -e`)
- **Nguyên nhân:** Lệnh `rofi -e` (error/message mode) sử dụng cây widget cứng `window -> error-message -> textbox`, bỏ qua hoàn toàn các tùy biến layout `mainbox`, `inputbar`, `children`. Do đó, box bị mất nền bo góc và chữ bị dồn trơ trọi về góc trái trên màn hình.
- **Giải pháp triệt để:**
  - Với Loading: Dùng `rofi -dmenu -p "Analyzing..." -theme-str "$THEME_LOADING" </dev/null &` với `inputbar { children: [ prompt ]; }`.
  - Với thông báo lỗi: Dùng `rofi -dmenu -mesg "$ERROR_DISPLAY" -theme-str "$THEME_RESULT"` hiển thị lỗi bên trong hộp thoại Glassmorphism trang trọng, căn giữa màn hình.

---

### 📌 Vấn đề 3: Lỗi chiều cao Response Box không co giãn theo chữ (cắt cụt dòng cuối) và đệm góc không đều
- **Hiện tượng lỗi:**
  - Khi nội dung dịch dài (>12 dòng), dòng cuối cùng luôn bị cắt ngang nửa chữ hoặc biến mất.
  - Văn bản bị dồn sát vào góc bo bên trái, trong khi bên phải thừa một khoảng đen trống trải rất lớn.
- **Nguyên nhân kỹ thuật:**
  1. *Lệch lề phải:* Chiều rộng `mainbox` đặt quá rộng (`850px`), trong khi văn bản căn trái và các câu dịch thông thường chỉ rộng 450-550px.
  2. *Cắt cụt chữ dòng cuối:* Pango Layout Engine trong Rofi khi đo kích thước bounding box của văn bản nhiều dòng (`pango_layout_get_pixel_size`) không tính đủ phần *descent* của font glyphs (các chữ có đuôi như `g, y, p, q`). Rofi cắt clip bề mặt ngay tại baseline của dòng cuối cùng.
  3. *Lồng ghép padding:* Khai báo padding phân tán ở cả `mainbox` và `textbox` làm sai lệch chiều cao thực tế được cấp phát.
- **Giải pháp triệt để:**
  - Cân bằng chiều rộng về kích thước vàng: `width: 760px;`, bo góc `border-radius: 20px;`.
  - Gom toàn bộ padding về một cấp duy nhất: `mainbox { padding: 24px 32px; }`, đồng thời đặt `message, textbox { padding: 0px; margin: 0px; }`.
  - **Kỹ thuật Newline Buffer:** Tự động nối ký tự xuống dòng đệm `\n` vào cuối nội dung hiển thị (`"$TRANSLATION"$'\n'`). Ký tự này mở rộng bounding box của Pango, đảm bảo dòng cuối cùng và toàn bộ các ký tự có đuôi hiển thị trọn vẹn 100% từ 3 dòng đến hơn 25 dòng.

---

### 📌 Vấn đề 4: Tối ưu độ trễ với Kiến trúc Hybrid (Cách B: Groq primary + Gemini fallback)
- **Bối cảnh:** Model Gemini trên endpoint `v1beta` có độ trễ khá cao (15s - 28s) do cơ chế suy nghĩ ngầm (CoT).
- **Giải pháp triển khai:**
  - **Groq API (Primary):** Tích hợp endpoint OpenAI-compatible (`https://api.groq.com/openai/v1/chat/completions`). Model `openai/gpt-oss-120b` (hoặc `qwen/qwen3.8-27b`) cho thời gian phản hồi cực nhanh (~0.6s - 1.5s) với chất lượng dịch chuẩn xác.
  - **Gemini API (Fallback):** Tự động kích hoạt khi `GROQ_API_KEY` trống hoặc request Groq thất bại. Thiết lập cờ cURL `-4` (IPv4) và `--max-time 45` để hạn chế lỗi timeout mạng.

---

### 📌 Vấn đề 5: Chuẩn hóa System Prompt phân nhánh và đánh giá ngữ pháp
Hệ thống sử dụng prompt thông minh tự động nhận diện ngôn ngữ và độ dài input:
- **Tiếng Anh sang Tiếng Việt:**
  - *Từ / Cụm từ (Format A):* Input (kèm phiên âm IPA) -> Meaning (tiếng Anh) -> Translation (tiếng Việt).
  - *Câu (Format B):* Input -> Evaluation (đánh giá ngữ pháp/ngữ nghĩa) -> Translation -> Keywords (danh sách từ vựng trọng tâm kèm nghĩa).
- **Tiếng Việt sang Tiếng Anh:**
  - *Từ / Cụm từ (Format C):* Từ gốc -> Tiếng Anh (danh sách các từ tương đương).
  - *Câu (Format D):* Câu gốc -> Bản dịch tiếng Anh chuẩn xác.

---

### 📌 Vấn đề 6: Bảo mật API Key và xóa sạch lịch sử Git Commit
- **Bối cảnh:** Trước đây API key từng bị vô tình commit trực tiếp vào mã nguồn Git.
- **Giải pháp xử lý triệt để:**
  1. Chuyển toàn bộ keys vào `config.env` và `~/.config/rofi-translate/config.env`, phân quyền `chmod 600`.
  2. Cập nhật `.gitignore` loại trừ tất cả các file cấu hình nhạy cảm.
  3. Tạo nhánh sạch không lịch sử (`git checkout --orphan temp-clean`), commit lại cây thư mục sạch và xóa sạch dấu vết bằng `git reflog expire --expire=now --all && git gc --prune=now --aggressive`.

---

## 3. Cấu trúc thư mục dự án chuẩn hóa

```
rofi_translate/
├── .env.example         # Template cấu hình mẫu (Groq + Gemini)
├── .gitignore           # Loại bỏ .env, config.env, log, scratch files
├── config.env           # File cấu hình chứa API key thật (được gitignore, chmod 600)
├── install.sh           # Script cài đặt tự động (symlink, desktop entry, kwin fade effect)
├── LICENSE              # Giấy phép mã nguồn mở MIT
├── README.md            # Tài liệu dự án cho người dùng cuối
├── context.md           # Nhật ký giải pháp kỹ thuật & Knowledge Base (file này)
└── rofi_translate.sh    # Script thực thi chính (bảo mật, kiến trúc Hybrid Groq/Gemini)
```