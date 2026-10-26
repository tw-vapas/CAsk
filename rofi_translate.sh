#!/bin/bash

# ==============================================================================
# ROFI AI TRANSLATOR (Wayland / Fedora / KDE Compatible)
# Glassmorphism Quick Translator powered by Google Gemini API
# ==============================================================================

set -o pipefail

# Thư mục và file cấu hình
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate"
CONFIG_FILE="$CONFIG_DIR/config.env"

# Tải cấu hình theo thứ tự ưu tiên:
# 1. ~/.config/rofi-translate/config.env
# 2. config.env nằm cùng thư mục script
# 3. .env nằm cùng thư mục script
if [ -f "$CONFIG_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
elif [ -f "$SCRIPT_DIR/config.env" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/config.env"
elif [ -f "$SCRIPT_DIR/.env" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
fi

# Cấu hình API - Cách B: Ưu tiên Groq siêu tốc, fallback qua Gemini
GROQ_API_KEY="${GROQ_API_KEY:-}"
GROQ_MODEL="${GROQ_MODEL:-openai/gpt-oss-120b}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}"

# ==============================================================================
# GIAO DIỆN THEME GLASSMORPHISM (Centering & Fit-to-content)
# ==============================================================================

# 1. Theme cho ô nhập liệu (Input) - Cửa sổ nổi 600px căn giữa, không che nền phía sau
THEME_INPUT="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter Display 14\"; }
  window {
    location: center;
    anchor: center;
    width: 600px;
    background-color: transparent;
    border: 0px;
    padding: 0px;
    margin: 0px;
  }
  mainbox {
    width: 600px;
    children: [ inputbar ];
    background-color: rgba(28, 28, 30, 0.95);
    border: 1px;
    border-color: rgba(255, 255, 255, 0.18);
    border-radius: 20px;
    padding: 10px 14px;
  }
  inputbar {
    children: [ entry ];
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 12px 18px;
  }
  entry {
    placeholder: \"Type your words...\";
    placeholder-color: rgba(255, 255, 255, 0.35);
    text-color: #ffffff;
    vertical-align: 0.5;
  }
"

# 2. Theme cho hộp thoại Loading - Đồng nhất 100% kích thước & vị trí với Input bar, không che nền
THEME_LOADING="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter Display 14\"; }
  window {
    location: center;
    anchor: center;
    width: 600px;
    background-color: transparent;
    border: 0px;
    padding: 0px;
    margin: 0px;
  }
  mainbox {
    width: 600px;
    children: [ inputbar ];
    background-color: rgba(28, 28, 30, 0.95);
    border: 1px;
    border-color: rgba(255, 255, 255, 0.18);
    border-radius: 20px;
    padding: 10px 14px;
  }
  inputbar {
    children: [ prompt ];
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 12px 18px;
  }
  prompt {
    text-color: #818cf8;
    horizontal-align: 0.0;
    vertical-align: 0.5;
    font: \"Inter Display 14\";
  }
"

# 3. Theme cho bảng kết quả (Result) - Fullscreen backdrop mờ, click ngoài để đóng, wrap chữ tự động
THEME_RESULT="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter 13\"; }
  window { fullscreen: true; background-color: rgba(10, 10, 10, 0.45); children: [ dummy-top, h-box, dummy-bottom ]; }
  dummy-top, dummy-bottom { expand: true; }
  h-box { orientation: horizontal; children: [ dummy-left, mainbox, dummy-right ]; expand: false; }
  dummy-left, dummy-right { expand: true; }
  mainbox { width: 850px; max-height: 85%; expand: false; children: [ message ]; background-color: rgba(28, 28, 30, 0.95); border: 1px; border-color: rgba(255, 255, 255, 0.18); border-radius: 24px; padding: 24px 28px; }
  message { padding: 0px; border: 0px; }
  textbox { text-color: #f3f4f6; padding: 12px 16px; wrap: true; font: \"Inter 13\"; }
"

# Cờ hỗ trợ xử lý chuột trên Wayland:
# - Click vào vùng nền mờ bên ngoài card -> kb-cancel (thoát)
ROFI_MOUSE_FLAGS=(
  -hover-select
  -me-select-entry ''
  -me-accept-entry '!MousePrimary'
  -kb-cancel 'Escape,MousePrimary'
)

# Đảm bảo dọn dẹp tiến trình Loading khi script thoát đột ngột
trap 'kill $LOADING_PID 2>/dev/null; exit 0' INT TERM EXIT

# ==============================================================================
# KIỂM TRA CẤU HÌNH API KEY
# ==============================================================================
if [ -z "$GROQ_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    NO_KEY_MSG="⚠️ Chưa cấu hình API Key!

Vui lòng cấu hình GROQ_API_KEY hoặc GEMINI_API_KEY vào:
$CONFIG_FILE
(Tham khảo mẫu cấu hình tại .env.example)"
    rofi -dmenu -mesg "$NO_KEY_MSG" -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
    exit 1
fi

# ==============================================================================
# BƯỚC 1: LẤY INPUT TỪ NGƯỜI DÙNG (CỬA SỔ NỔI, TƯƠNG TÁC ĐƯỢC VỚI NỀN)
# ==============================================================================
INPUT=$(rofi -dmenu -theme-str "$THEME_INPUT" -kb-cancel 'Escape')
if [ -z "$INPUT" ]; then exit 0; fi

# ==============================================================================
# BƯỚC 2: HIỂN THỊ LOADING BOX (CỬA SỔ NỔI, TƯƠNG TÁC ĐƯỢC VỚI NỀN)
# ==============================================================================
rofi -dmenu -p "Analyzing..." -theme-str "$THEME_LOADING" </dev/null &
LOADING_PID=$!

# ==============================================================================
# BƯỚC 3: GỌI API (CÁCH B: ƯU TIÊN GROQ ~0.6S -> FALLBACK GEMINI DỰ PHÒNG)
# ==============================================================================
SYSTEM_PROMPT="Bạn là một biên dịch viên thông thạo.
Nếu input là en thì dịch qua vi, nếu input là vi thì dịch qua en

Hãy trình bày theo đúng định dạng sau, bản dịch phải dễ hiểu

Nếu là en to vithì áp dụng format A với B
Nếu là vi to en thì áp dụng format C với D

Format A (Input là từ/cụm từ):
• Input: {Từ gốc en} - {Phiên âm IPA}
• Meaning: {Nghĩa en}
• Translation: {Bản dịch vi}

Format B (Input là câu):
• Input: {Câu gốc en}
• Translation: {Bản dịch vi}
• Keywords:
{tab}• {từ vựng en}: {bản dịch từ vựng vi}

Formar C (Input là từ/cụm từ):
• Từ gốc: {Từ gốc vi}
• Tiếng Anh: 
{tab}• {Các từ tương ứng trong tiếng Anh}: {Bản dịch vi}

Format D (Input là câu)
• Câu gốc: {Câu gốc vi}
• Bản dịch: {Bản dịch en}"

TRANSLATION=""
ERROR_MSG=""

# 3.1. Ưu tiên 1: Groq API (Tốc độ cực nhanh ~0.5s - 0.8s)
if [ -n "$GROQ_API_KEY" ]; then
    GROQ_PAYLOAD=$(jq -n \
      --arg model "$GROQ_MODEL" \
      --arg sys "$SYSTEM_PROMPT" \
      --arg input "$INPUT" \
      '{
        model: $model,
        messages: [
          {role: "system", content: $sys},
          {role: "user", content: ("Nội dung cần dịch: " + $input)}
        ],
        temperature: 0.2,
        max_tokens: 1000
      }')

    GROQ_RESPONSE=$(curl -4 -s --connect-timeout 5 --max-time 15 -X POST "https://api.groq.com/openai/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $GROQ_API_KEY" \
      -d "$GROQ_PAYLOAD")

    TRANSLATION=$(echo "$GROQ_RESPONSE" | jq -r '.choices[0].message.content // empty')
    if [ -z "$TRANSLATION" ]; then
        ERROR_MSG=$(echo "$GROQ_RESPONSE" | jq -r '.error.message // empty')
    fi
fi

# 3.2. Ưu tiên 2: Fallback sang Google Gemini API nếu Groq thất bại hoặc chưa cấu hình
if [ -z "$TRANSLATION" ] && [ -n "$GEMINI_API_KEY" ]; then
    GEMINI_PAYLOAD=$(jq -n \
      --arg prompt "$SYSTEM_PROMPT" \
      --arg input "$INPUT" \
      '{contents: [{parts: [{text: ($prompt + "\n\nNội dung cần dịch: " + $input)}]}]}')

    GEMINI_RESPONSE=$(curl -4 -s --connect-timeout 8 --max-time 45 -X POST "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=$GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -d "$GEMINI_PAYLOAD")

    TRANSLATION=$(echo "$GEMINI_RESPONSE" | jq -r '.candidates[0].content.parts[0].text // empty')
    if [ -z "$TRANSLATION" ]; then
        GEMINI_ERR=$(echo "$GEMINI_RESPONSE" | jq -r '.error.message // empty')
        if [ -n "$GEMINI_ERR" ]; then
            ERROR_MSG="$GEMINI_ERR"
        fi
    fi
fi

# Tắt cửa sổ Loading ngay khi hoàn tất
kill $LOADING_PID 2>/dev/null
wait $LOADING_PID 2>/dev/null

# ==============================================================================
# BƯỚC 4: HIỂN THỊ KẾT QUẢ (FIT VỚI NỘI DUNG, ENTER / ESC / CLICK OUT ĐỂ ĐÓNG)
# ==============================================================================
if [ -n "$TRANSLATION" ]; then
    # Tự động sao chép kết quả vào clipboard trong nền
    if command -v wl-copy >/dev/null 2>&1; then
        echo -n "$TRANSLATION" | wl-copy &
    elif command -v xclip >/dev/null 2>&1; then
        echo -n "$TRANSLATION" | xclip -selection clipboard &
    fi

    # Hiển thị kết quả bằng dmenu, container fit nội dung, đóng bằng Enter/Esc hoặc click ngoài
    rofi -dmenu -mesg "$TRANSLATION" -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
else
    if [ -z "$ERROR_MSG" ]; then
        ERROR_MSG="Không nhận được phản hồi từ AI API (kết nối timeout hoặc mạng không ổn định)."
    fi

    ERROR_DISPLAY="❌ Lỗi dịch thuật:

$ERROR_MSG"
    rofi -dmenu -mesg "$ERROR_DISPLAY" -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
fi
