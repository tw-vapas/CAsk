# Quick Translator (Rofi + Google Gemini trên Fedora Linux / Wayland KDE Plasma)

Tài liệu này lưu trữ toàn bộ kiến trúc, nguyên nhân lỗi và giải pháp kỹ thuật đã xử lý để các session sau có thể kế thừa và bảo trì ngay lập tức.

---

## 1. Môi trường & Luồng hoạt động (Architecture & Workflow)
- **Hệ điều hành:** Fedora Linux
- **Môi trường hiển thị:** Wayland (Compositor: KDE Plasma 6 / KWin)
- **Công cụ UI:** Rofi (phiên bản `2.0.0` tích hợp Wayland layer-shell / XCB)
- **Backend AI:** Google Gemini API qua `curl` và `jq`
- **Clipboard:** `wl-copy` (Wayland native)
- **Quản lý cấu hình:** `~/.config/rofi-translate/config.env` (bảo mật, không commit lên Git)

### Luồng xử lý (Workflow):
1. **Bước 1 (Input):** Mở Rofi hiển thị thanh nhập text dạng capsule căn giữa màn hình với nền mờ Glassmorphism. Nhập text và nhấn `Enter` (hoặc nhấn `Esc` / click ra ngoài nền mờ để đóng).
2. **Bước 2 (Loading):** Chuyển sang hộp thoại `✨ AI đang phân tích và dịch...` có cùng kích thước (600px), vị trí và padding với thanh Search (tạo cảm giác chuyển đổi mượt mà, liền mạch, không giật nhảy layout).
3. **Bước 3 (API Request):** Gửi prompt định dạng qua `curl` đến Google Gemini API (model `gemini-3.5-flash-lite`).
4. **Bước 4 (Hiển thị kết quả):** Tắt Loading, mở cửa sổ kết quả đa dòng fit hoàn toàn theo nội dung dịch. Tự động copy vào clipboard trong nền (`wl-copy`). Nhấn `Enter`, `Esc` hoặc click chuột ra ngoài nền mờ để đóng cửa sổ ngay tức thì.

---

## 2. Các vấn đề kỹ thuật cốt lõi và cách xử lý (Knowledge Base)

### 📌 Vấn đề 1: Lỗi gọi Gemini API 404 (`NOT_FOUND`)
- **Triệu chứng:** Gọi `models/gemini-1.5-flash` hoặc `gemini-1.5-flash-latest` trên API `v1beta` bị trả về lỗi:
  ```json
  "models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent"
  ```
- **Nguyên nhân:** Google đã ngừng hỗ trợ (sunset/deprecate) dòng model Gemini 1.5 trên endpoint `v1beta`. Các bản 2.0/2.5 cũng bị khóa cho tài khoản mới.
- **Giải pháp:** Sử dụng model **`gemini-3.5-flash-lite`** (endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=...`). Model này phản hồi trong dưới 2 giây, hỗ trợ đầy đủ tiếng Việt và định dạng ví dụ từ vựng.

---

### 📌 Vấn đề 2: Cờ `-click-to-exit` của Rofi không hoạt động trên Wayland
- **Triệu chứng:** Gắn cờ `-click-to-exit` nhưng click chuột ra ngoài cửa sổ Rofi không đóng lại.
- **Nguyên nhân:**
  1. Trên X11, Rofi dùng `XGrabPointer` để bắt toàn cục sự kiện chuột.
  2. Trên Wayland (KWin), nguyên tắc bảo mật cô lập từng surface. Cửa sổ Rofi (nếu chỉ rộng 600px) chỉ nhận được sự kiện chuột **bên trong diện tích của nó**. Click ra ngoài sẽ đi thẳng vào desktop/cửa sổ khác, Rofi hoàn toàn không nhận được click event.
  3. Lệnh `rofi -e` chỉ là dialog tĩnh, không hỗ trợ mouse event loop.
- **Giải pháp triệt để:**
  - **Phân tách trải nghiệm chuột theo từng khâu:**
    - **Khâu Input & Loading:** Dùng cửa sổ nổi 600px không chiếm toàn màn hình (`window { location: center; anchor: center; width: 600px; }`), chỉ bắt phím <kbd>Escape</kbd>. Người dùng có thể nhìn thấy trọn vẹn và tương tác click chuột bình thường với các cửa sổ phía sau.
    - **Khâu Response:** Kích hoạt lớp phủ mờ Glassmorphism bao phủ 100% màn hình (`window { fullscreen: true; background-color: rgba(10, 10, 10, 0.45); }`) kết hợp cờ chuột `-hover-select -me-select-entry '' -me-accept-entry '!MousePrimary' -kb-cancel 'Escape,MousePrimary'`. Click vào bất cứ đâu bên ngoài Response Box sẽ đóng cửa sổ ngay lập tức.

---

### 📌 Vấn đề 3: Hiệu ứng cửa sổ "thu vào / phóng ra" (Scale Animation) làm mất thẩm mỹ
- **Triệu chứng:** Khi Rofi mở ra hoặc đóng lại (nhất là giữa các bước Input -> Loading -> Result), cửa sổ có hiệu ứng thu nhỏ dần vào tâm rồi biến mất (`Scale` effect của KWin) thay vì mờ dần (`Fade`).
- **Nguyên nhân:** Trên KDE Plasma 6 Wayland, KWin kích hoạt hiệu ứng `scale` mặc định cho việc đóng/mở cửa sổ.
- **Giải pháp:** Tắt hiệu ứng `scale` và kích hoạt hiệu ứng `fade` trong KWin:
  ```bash
  kwriteconfig6 --file kwinrc --group Plugins --key scaleEnabled false
  kwriteconfig6 --file kwinrc --group Plugins --key fadeEnabled true
  qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect "scale"
  qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect "fade"
  qdbus-qt6 org.kde.KWin /KWin org.kde.KWin.reconfigure
  ```

---

### 📌 Vấn đề 4: Tinh chỉnh UI/UX Aesthetic
1. **Container của input field bị khoảng trống thừa bên dưới & Placeholder:**
   - Xảy ra khi dùng `padding` phần trăm trên `window` khiến `mainbox` bị ép giãn chiều cao.
   - **Xử lý:** Dùng layout 3 tầng với các spacer đệm `dummy`:
     ```rasi
     window { children: [ dummy-top, h-box, dummy-bottom ]; }
     h-box { orientation: horizontal; children: [ dummy-left, mainbox, dummy-right ]; }
     mainbox { width: 600px; expand: false; ... }
     ```
     `expand: false` giúp `mainbox` chỉ ôm vừa khít chiều cao của `inputbar`, không thừa khoảng trống. Placeholder đặt là `"Type your words..."`.
2. **Container Loading đồng bộ 100% với Input bar & Khắc phục lỗi `rofi -e`:**
   - **Phát hiện cốt lõi:** Lệnh `rofi -e` (error dialog) chỉ sinh ra cấu trúc cây widget cứng `window -> error-message -> textbox`, nó hoàn toàn bỏ qua các định nghĩa `children: [ dummy-top, h-box, dummy-bottom ]`, `mainbox` và `inputbar`. Do đó, nếu dùng `rofi -e`, mọi style container (màu nền mờ, bo góc, width 600px, centering) đều bị mất và chữ "Analyzing..." sẽ bị văng trơ trọi lên góc màn hình.
   - **Giải pháp triệt để:** Dùng `rofi -dmenu -p "Analyzing..." -theme-str "$THEME_LOADING" </dev/null &`.
   - Trong `THEME_LOADING`, cấu trúc widget là `mainbox { width: 600px; children: [ inputbar ]; }` và `inputbar { children: [ prompt ]; }`. `prompt` mang chữ `"Analyzing..."` căn lề trái (`horizontal-align: 0.0; vertical-align: 0.5;`), dùng cùng font `Inter Display 14` với thanh input.
   - Kết quả: Khi chuyển cảnh, chính thanh input vừa gõ biến đổi tại chỗ thành thanh loading với kích thước và vị trí trùng khít 100%.
3. **Cửa sổ Response: Khắc phục cắt chữ ở đáy & góc:**
   - **Nguyên nhân cắt chữ:** Khi `message` và `textbox` có padding bằng 0 trong `mainbox`, thuật toán tính chiều cao của Rofi bị hụt chiều cao dòng cuối cùng (khiến dòng chữ cuối bị cắt ngang phân nửa).
   - **Giải pháp:** Mở rộng `width: 850px;`, đặt `mainbox { padding: 24px 28px; border-radius: 24px; }` và `textbox { padding: 12px 16px; }`. Khoảng đệm phân tầng này giúp Rofi tính toán chính xác 100% chiều cao của khối văn bản Pango, dòng cuối cùng luôn nguyên vẹn và 4 góc bo viền có khoảng cách an toàn so với nội dung chữ.

---

### 📌 Vấn đề 6: Timeout cURL và hiển thị lỗi dịch thuật trong Response Box
- **Triệu chứng:** Thường xuyên gặp thông báo `❌ Lỗi dịch thuật:\n...` dưới dạng văn bản tím ở góc trên bên trái màn hình.
- **Nguyên nhân cốt lõi:**
  1. **Timeout cURL:** Tham số `--max-time 15` quá ngắn khi mạng chậm hoặc model Gemini suy nghĩ lâu (có thể mất 20-30s). Curl bị hủy ngang và không nhận được nội dung, sinh ra lỗi timeout.
  2. **Chuỗi `\n` bị hiển thị nguyên văn:** Trong bash, chuỗi `"❌ Lỗi dịch thuật:\n$ERROR_MSG"` trong dấu ngoặc kép không tự escape ký tự `\n` thành xuống dòng.
  3. **Lỗi UI văng góc trái:** Dùng `rofi -e` với `$THEME_LOADING` làm Rofi bỏ qua toàn bộ container và chỉ hiện chữ ở góc màn hình.
- **Giải pháp:**
  - Tối ưu cURL: Thêm cờ `-4` (bỏ qua IPv6 bị unreachable) và nâng `--max-time` lên `45` giây kết hợp `--connect-timeout 8`.
  - Hiển thị lỗi qua `rofi -dmenu -mesg "$ERROR_DISPLAY" -theme-str "$THEME_RESULT"`, giúp thông báo lỗi xuất hiện trang trọng bên trong Response Box bo góc 24px, căn giữa, đóng mở bằng Enter/Esc/Click chuột ngoài.

---

### 📌 Vấn đề 7: Tối ưu độ trễ với Cách B (Hybrid Groq primary + Gemini fallback)
- **Bối cảnh:** Gemini API trên v1beta có thời gian sinh kết quả từ 15-28s (do mô hình chạy CoT suy nghĩ ngầm). Điều này làm gián đoạn trải nghiệm dịch nhanh của người dùng.
- **Giải pháp Cách B:**
  - **Ưu tiên 1 (Groq Cloud API):** Sử dụng `llama-3.3-70b-versatile` qua endpoint OpenAI-compatible (`https://api.groq.com/openai/v1/chat/completions`). Thời gian xử lý chỉ ~**0.6 giây**.
  - **Ưu tiên 2 (Fallback Google Gemini API):** Tự động kích hoạt khi Groq API key không tồn tại, hết hạn, chạm rate limit hoặc kết nối lỗi.
  - **Bảo mật tuyệt đối:** Lưu trữ toàn bộ key trong `config.env` và `~/.config/rofi-translate/config.env` với phân quyền `chmod 600`. File này được ghi vào `.gitignore` để không bao giờ bị lộ lên git repository.

---

## 3. Cấu trúc thư mục dự án chuẩn hóa

```
rofi_translate/
├── .env.example         # Template cấu hình API key
├── .gitignore           # Loại bỏ .env, config.env, log, temp files
├── install.sh           # Script cài đặt tự động (symlink, desktop entry, kwin effect)
├── LICENSE              # Giấy phép mã nguồn mở MIT
├── README.md            # Tài liệu dự án hoàn chỉnh
├── context.md           # Nhật ký giải pháp kỹ thuật & Knowledge Base
└── rofi_translate.sh    # Script thực thi chính (bảo mật, không hardcode API key)
```