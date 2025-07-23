from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime
import base64, numpy as np, cv2, time

app = Flask(__name__)

EMO = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]

# 全域暫存最後一次預測，用來匯出報告
last_prediction = {
    "label": "-(尚無資料)-",
    "probabilities": [0]*len(EMO),
    "timestamp": "N/A"
}

def fake_predict():
    """隨機產生七類情緒機率並回傳最高機率情緒標籤與機率分布"""
    np.random.seed(int(time.time()*1000) % 100000)
    probs = np.random.dirichlet(np.ones(len(EMO)))
    return EMO[int(np.argmax(probs))], probs.tolist()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    global last_prediction
    data = request.get_json()
    # 將 base64 字串轉成影像 (目前 demo 未用到，可替換成真模型前處理)
    image_data = data['image'].split(',')[1]
    img_bytes = base64.b64decode(image_data)
    img_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

    # === 模型推論（此處用假模型） ===
    label, probs = fake_predict()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    last_prediction = {
        "label": label,
        "probabilities": probs,
        "timestamp": timestamp
    }
    return jsonify({'label': label})

@app.route('/export', methods=['GET'])
def export_pdf():
    """將 last_prediction 輸出為 PDF 並下載"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # 標題
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h-50, "情緒興趣建議報告")

    # 基本資訊
    c.setFont("Helvetica", 12)
    c.drawString(50, h-90, f"辨識時間：{last_prediction['timestamp']}")
    c.drawString(50, h-110, f"主要情緒：{last_prediction['label']}")

    # 機率表
    y = h - 150
    for emo, p in zip(EMO, last_prediction['probabilities']):
        c.drawString(70, y, f"{emo:<10}: {p:.3f}")
        y -= 18

    # 興趣/建議 (示例)
    suggestion_map = {
        "Happy": "孩子對當前活動充滿興趣，建議延伸相關主題以維持動機。",
        "Sad": "可能對內容感到挫折，可嘗試以故事或遊戲化方式重新引導。",
        "Angry": "顯示高挫折感，建議暫停並給予正向回饋。"
    }
    advice = suggestion_map.get(last_prediction['label'], "觀察更多資料以進一步分析興趣傾向。")

    c.drawString(50, y-20, "興趣建議：")
    c.setFont("Helvetica", 12)
    c.drawString(70, y-40, advice)

    c.showPage()
    c.save()
    buffer.seek(0)
    fname = f"emotion_report_{last_prediction['timestamp'].replace(':', '-')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=fname, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)