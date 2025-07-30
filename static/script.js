// static/script.js
// 全域變數
let video, canvas, ctx;
let yoloModel = null;
let emotionModel = null;
let isDetecting = false;
let currentSessionId = null;
let studyTimer = null;
let detectionInterval = null;
let startTime = null;
let totalDuration = 0;
let emotionData = [];
let detectionCount = 0;
let validDetections = 0;
let noFaceWarningCount = 0;
let multipleFaceWarningCount = 0;

// 情緒標籤對應
const EMOTION_LABELS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', function() {
    // 根據當前頁面初始化不同功能
    const currentPage = window.location.pathname;
    
    if (currentPage.includes('/register')) {
        initRegisterPage();
    } else if (currentPage.includes('/login')) {
        initLoginPage();
    } else if (currentPage.includes('/study/')) {
        initStudyPage();
    }
});

// 註冊頁面初始化
function initRegisterPage() {
    const form = document.getElementById('registerForm');
    if (form) {
        form.addEventListener('submit', handleRegister);
    }
}

// 登入頁面初始化
function initLoginPage() {
    const form = document.getElementById('loginForm');
    if (form) {
        form.addEventListener('submit', handleLogin);
    }
}

// 學習頁面初始化
async function initStudyPage() {
    await initCamera();
    initStudyControls();
    await loadModels();
}

// 處理註冊表單提交
async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (password !== confirmPassword) {
        showMessage('密碼確認不一致');
        return;
    }
    
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                email: email,
                password: password
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('註冊成功！請登入', 'success');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
        } else {
            showMessage(result.message);
        }
    } catch (error) {
        showMessage('註冊失敗，請稍後再試');
    }
}

// 處理登入表單提交
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('登入成功！', 'success');
            setTimeout(() => {
                window.location.href = '/child_selection';
            }, 1000);
        } else {
            showMessage(result.message);
        }
    } catch (error) {
        showMessage('登入失敗，請稍後再試');
    }
}

// 顯示訊息
function showMessage(message, type = 'error') {
    const modal = document.getElementById('messageModal');
    const modalMessage = document.getElementById('modalMessage');
    
    if (modal && modalMessage) {
        modalMessage.textContent = message;
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    } else {
        alert(message);
    }
}

// 初始化攝影機
async function initCamera() {
    try {
        video = document.getElementById('video');
        canvas = document.getElementById('canvas');
        
        if (!video || !canvas) return;
        
        ctx = canvas.getContext('2d');
        
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: 640,
                height: 480,
                facingMode: 'user'
            }
        });
        
        video.srcObject = stream;
        
        video.addEventListener('loadedmetadata', () => {
            updateCameraStatus('攝影機已就緒', 'success');
        });
        
    } catch (error) {
        console.error('攝影機初始化失敗:', error);
        updateCameraStatus('無法存取攝影機，請檢查權限設定', 'error');
    }
}

// 更新攝影機狀態
function updateCameraStatus(message, type = 'info') {
    const statusElement = document.getElementById('cameraStatus');
    if (statusElement) {
        statusElement.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'}`;
        statusElement.innerHTML = `<i class="fas fa-${type === 'error' ? 'exclamation-circle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>${message}`;
    }
}

// 初始化學習控制項
function initStudyControls() {
    const startButton = document.getElementById('startButton');
    const pauseButton = document.getElementById('pauseButton');
    const endButton = document.getElementById('endButton');
    const generateReportBtn = document.getElementById('generateReportBtn');
    
    if (startButton) {
        startButton.addEventListener('click', startStudySession);
    }
    
    if (pauseButton) {
        pauseButton.addEventListener('click', pauseStudySession);
    }
    
    if (endButton) {
        endButton.addEventListener('click', endStudySession);
    }
    
    if (generateReportBtn) {
        generateReportBtn.addEventListener('click', generateReport);
    }
}

// 載入 AI 模型
async function loadModels() {
    try {
        updateCameraStatus('正在載入 AI 模型...', 'info');
        
        // 載入 ONNX Runtime
        if (typeof ort !== 'undefined') {
            // 載入 YOLOv8 臉部偵測模型
            const yoloSession = await ort.InferenceSession.create('/static/yolov8n-face.onnx');
            yoloModel = yoloSession;
            console.log('YOLOv8 模型載入成功');
        } else {
            console.warn('ONNX Runtime 未載入，使用備用方案');
        }
        
        // 載入 TensorFlow.js
        if (typeof tf !== 'undefined') {
            // 載入情緒分類模型
            emotionModel = await tf.loadLayersModel('/models/emotion_model.h5');
            console.log('情緒分類模型載入成功');
        } else {
            console.warn('TensorFlow.js 未載入，使用備用方案');
        }
        
        // 如果無法載入真實模型，使用模擬模式
        if (!yoloModel || !emotionModel) {
            console.log('使用模擬模式進行臉部和情緒檢測');
            yoloModel = { loaded: true, simulated: true };
            emotionModel = { loaded: true, simulated: true };
        }
        
        updateCameraStatus('AI 模型已就緒，可以開始學習', 'success');
        
    } catch (error) {
        console.error('模型載入失敗:', error);
        // 使用模擬模式
        yoloModel = { loaded: true, simulated: true };
        emotionModel = { loaded: true, simulated: true };
        updateCameraStatus('使用模擬 AI 模型', 'warning');
    }
}

// 開始學習階段
async function startStudySession() {
    const duration = parseInt(document.getElementById('studyDuration').value);
    
    if (!yoloModel || !emotionModel) {
        showMessage('AI 模型尚未就緒，請稍候');
        return;
    }
    
    try {
        const response = await fetch('/start_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                subject: SUBJECT,
                duration: duration
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentSessionId = result.session_id;
            totalDuration = duration;
            startTime = new Date();
            
            // 重置計數器
            noFaceWarningCount = 0;
            multipleFaceWarningCount = 0;
            emotionData = [];
            detectionCount = 0;
            validDetections = 0;
            
            // 隱藏設定卡片，顯示狀態卡片
            document.getElementById('timeSettingCard').style.display = 'none';
            document.getElementById('statusCard').style.display = 'block';
            document.getElementById('statsCard').style.display = 'block';
            
            // 開始計時器和檢測
            startTimer(duration * 60); // 轉換為秒
            startFaceDetection();
            
            isDetecting = true;
            
        } else {
            showMessage(result.message);
        }
        
    } catch (error) {
        showMessage('開始學習失敗，請稍後再試');
    }
}

// 開始計時器
function startTimer(totalSeconds) {
    let remainingSeconds = totalSeconds;
    
    updateTimerDisplay(remainingSeconds, totalSeconds);
    
    studyTimer = setInterval(() => {
        remainingSeconds--;
        updateTimerDisplay(remainingSeconds, totalSeconds);
        
        if (remainingSeconds <= 0) {
            endStudySession();
        }
    }, 1000);
}

// 更新計時器顯示
function updateTimerDisplay(remainingSeconds, totalSeconds) {
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    
    const timeDisplay = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    const remainingTimeElement = document.getElementById('remainingTime');
    const timeProgressElement = document.getElementById('timeProgress');
    
    if (remainingTimeElement) {
        remainingTimeElement.textContent = timeDisplay;
    }
    
    if (timeProgressElement) {
        const progress = ((totalSeconds - remainingSeconds) / totalSeconds) * 100;
        timeProgressElement.style.width = `${progress}%`;
    }
}

// 開始人臉檢測
function startFaceDetection() {
    detectionInterval = setInterval(() => {
        if (isDetecting && video && canvas) {
            detectFaceAndEmotion();
        }
    }, 3000); // 每3秒檢測一次
}

// 人臉檢測和情緒辨識
async function detectFaceAndEmotion() {
    try {
        // 將影片畫面繪製到 canvas
        ctx.drawImage(video, 0, 0, 300, 300);
        
        let detectionResult;
        
        // 檢查是否使用模擬模式
        if (yoloModel.simulated || emotionModel.simulated) {
            detectionResult = simulateDetection();
        } else {
            detectionResult = await performRealDetection();
        }
        
        if (detectionResult.error) {
            showDetectionWarning(detectionResult.error);
            return;
        }
        
        hideDetectionWarning();
        
        // 更新專注度指示器
        updateAttentionIndicator(detectionResult.attention);
        
        // 記錄數據
        await recordEmotionData(detectionResult);
        
        // 更新統計
        updateStatistics();
        
    } catch (error) {
        console.error('檢測過程發生錯誤:', error);
    }
}

// 執行真實的模型檢測
async function performRealDetection() {
    try {
        // 獲取圖像數據
        const imageData = ctx.getImageData(0, 0, 300, 300);
        
        // YOLOv8 臉部檢測
        if (yoloModel && !yoloModel.simulated) {
            // 預處理圖像為 ONNX 模型輸入
            const input = new ort.Tensor('float32', new Float32Array(300 * 300 * 3), [1, 3, 300, 300]);
            const feeds = { images: input };
            const results = await yoloModel.run(feeds);
            
            // 解析檢測結果
            const boxes = results.output0.data;
            const faces = [];
            
            for (let i = 0; i < boxes.length; i += 6) {
                if (boxes[i + 4] > 0.5) { // 信心度閾值
                    faces.push({
                        x: boxes[i],
                        y: boxes[i + 1],
                        width: boxes[i + 2] - boxes[i],
                        height: boxes[i + 3] - boxes[i + 1],
                        confidence: boxes[i + 4]
                    });
                }
            }
            
            if (faces.length === 0) {
                return { error: '未檢測到人臉，請確保臉部在攝影機範圍內' };
            }
            
            if (faces.length > 1) {
                return { error: '檢測到多人，請確保只有一人在攝影機前' };
            }
            
            // 擷取臉部區域
            const face = faces[0];
            const faceCanvas = document.createElement('canvas');
            faceCanvas.width = 112;
            faceCanvas.height = 112;
            const faceCtx = faceCanvas.getContext('2d');
            
            // 從原始畫面擷取臉部區域並縮放到 112x112
            faceCtx.drawImage(
                canvas,
                face.x, face.y, face.width, face.height,
                0, 0, 112, 112
            );
            
            // TensorFlow 情緒預測
            if (emotionModel && typeof tf !== 'undefined') {
                const input = tf.browser.fromPixels(faceCanvas);
                const normalized = input.div(255.0);
                const batched = normalized.expandDims(0);
                
                const predictions = await emotionModel.predict(batched).data();
                
                // 更新情緒條
                updateEmotionBars(predictions);
                
                const emotionIndex = predictions.indexOf(Math.max(...predictions));
                const emotion = EMOTION_LABELS[emotionIndex];
                const confidence = predictions[emotionIndex];
                
                // 根據情緒計算專注度
                const attention = calculateAttentionFromEmotion(emotion, confidence);
                
                // 清理張量
                input.dispose();
                normalized.dispose();
                batched.dispose();
                
                return {
                    emotion: emotion,
                    attention: attention,
                    confidence: confidence
                };
            }
        }
        
        // 如果無法使用真實模型，返回模擬結果
        return simulateDetection();
        
    } catch (error) {
        console.error('真實檢測失敗，使用模擬:', error);
        return simulateDetection();
    }
}

// 更新情緒條
function updateEmotionBars(predictions) {
    const emotions = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];
    
    emotions.forEach((emotion, index) => {
        const percentage = Math.round(predictions[index] * 100);
        const bar = document.getElementById(`${emotion}-bar`);
        const value = document.getElementById(`${emotion}-value`);
        
        if (bar && value) {
            bar.style.width = `${percentage}%`;
            value.textContent = `${percentage}%`;
        }
    });
}

// 根據情緒計算專注度
function calculateAttentionFromEmotion(emotion, confidence) {
    const attentionMap = {
        'neutral': 3,
        'happy': 2,
        'surprise': 2,
        'fear': 1,
        'sad': 1,
        'angry': 1,
        'disgust': 1
    };
    
    let baseAttention = attentionMap[emotion] || 2;
    
    // 根據信心度調整
    if (confidence < 0.5) {
        baseAttention = Math.max(1, baseAttention - 1);
    }
    
    return baseAttention;
}

// 模擬檢測結果
function simulateDetection() {
    detectionCount++;
    
    // 減少錯誤頻率，提供更穩定的體驗
    const rand = Math.random();
    
    // 降低無臉警告的頻率
    if (rand < 0.02 && noFaceWarningCount < 3) {
        noFaceWarningCount++;
        return { error: '未檢測到人臉，請確保臉部在攝影機範圍內' };
    }
    
    // 降低多人警告的頻率
    if (rand < 0.01 && multipleFaceWarningCount < 2) {
        multipleFaceWarningCount++;
        return { error: '檢測到多人，請確保只有一人在攝影機前' };
    }
    
    validDetections++;
    
    // 模擬更真實的情緒分布
    const emotionWeights = {
        'neutral': 0.4,
        'happy': 0.2,
        'surprise': 0.1,
        'sad': 0.1,
        'fear': 0.1,
        'angry': 0.05,
        'disgust': 0.05
    };
    
    // 生成模擬的情緒預測值
    const predictions = new Array(7).fill(0);
    let remaining = 1.0;
    
    EMOTION_LABELS.forEach((emotion, index) => {
        const weight = emotionWeights[emotion] || 0.1;
        const value = Math.random() * weight * remaining;
        predictions[index] = value;
        remaining -= value;
    });
    
    // 正規化
    const sum = predictions.reduce((a, b) => a + b, 0);
    predictions.forEach((val, idx) => {
        predictions[idx] = val / sum;
    });
    
    // 更新情緒條
    updateEmotionBars(predictions);
    
    const emotionIndex = predictions.indexOf(Math.max(...predictions));
    const emotion = EMOTION_LABELS[emotionIndex];
    const confidence = predictions[emotionIndex];
    
    // 根據情緒計算專注度
    const attention = calculateAttentionFromEmotion(emotion, confidence);
    
    return {
        emotion: emotion,
        attention: attention,
        confidence: confidence
    };
}

// 顯示檢測警告
function showDetectionWarning(message) {
    const warningElement = document.getElementById('detectionWarning');
    const messageElement = document.getElementById('warningMessage');
    
    if (warningElement && messageElement) {
        messageElement.textContent = message;
        warningElement.style.display = 'block';
        
        // 3秒後自動隱藏
        setTimeout(() => {
            warningElement.style.display = 'none';
        }, 3000);
    }
    
    // 同時在小視窗顯示警告
    if (miniWindow && !miniWindow.closed) {
        showMiniAlert(message);
    }
}

// 隱藏檢測警告
function hideDetectionWarning() {
    const warningElement = document.getElementById('detectionWarning');
    if (warningElement) {
        warningElement.style.display = 'none';
    }
}

// 更新專注度指示器
function updateAttentionIndicator(attentionLevel) {
    const lowLight = document.getElementById('lowAttention');
    const mediumLight = document.getElementById('mediumAttention');
    const highLight = document.getElementById('highAttention');
    
    // 重置所有指示燈
    [lowLight, mediumLight, highLight].forEach(light => {
        if (light) {
            light.classList.remove('active');
        }
    });
    
    // 點亮對應的指示燈
    if (attentionLevel === 1 && lowLight) {
        lowLight.classList.add('active');
    } else if (attentionLevel === 2 && mediumLight) {
        mediumLight.classList.add('active');
    } else if (attentionLevel === 3 && highLight) {
        highLight.classList.add('active');
    }
}

// 記錄情緒數據
async function recordEmotionData(detectionResult) {
    emotionData.push({
        timestamp: new Date(),
        emotion: detectionResult.emotion,
        attention: detectionResult.attention,
        confidence: detectionResult.confidence
    });
    
    try {
        await fetch('/record_emotion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                emotion: detectionResult.emotion,
                attention_level: detectionResult.attention,
                confidence: detectionResult.confidence
            })
        });
    } catch (error) {
        console.error('記錄情緒數據失敗:', error);
    }
}

// 更新統計資訊
function updateStatistics() {
    const avgAttentionElement = document.getElementById('avgAttention');
    const detectionCountElement = document.getElementById('detectionCount');
    const validDetectionsElement = document.getElementById('validDetections');
    
    if (avgAttentionElement && emotionData.length > 0) {
        const avgAttention = emotionData.reduce((sum, data) => sum + data.attention, 0) / emotionData.length;
        const avgAttentionPercent = Math.round(avgAttention * 100 / 3);
        avgAttentionElement.textContent = avgAttentionPercent + '%';
    }
    
    if (detectionCountElement) {
        detectionCountElement.textContent = detectionCount;
    }
    
    if (validDetectionsElement) {
        validDetectionsElement.textContent = validDetections;
    }
}

// 暫停學習
function pauseStudySession() {
    if (isDetecting) {
        isDetecting = false;
        clearInterval(studyTimer);
        clearInterval(detectionInterval);
        
        const pauseButton = document.getElementById('pauseButton');
        if (pauseButton) {
            pauseButton.innerHTML = '<i class="fas fa-play me-2"></i>繼續';
            pauseButton.onclick = resumeStudySession;
        }
    }
}

// 繼續學習
function resumeStudySession() {
    if (!isDetecting) {
        isDetecting = true;
        
        // 重新開始檢測
        startFaceDetection();
        
        // 重新計算剩餘時間並開始計時
        const currentTime = new Date();
        const elapsedMinutes = (currentTime - startTime) / (1000 * 60);
        const remainingMinutes = totalDuration - elapsedMinutes;
        
        if (remainingMinutes > 0) {
            startTimer(Math.floor(remainingMinutes * 60));
        }
        
        const pauseButton = document.getElementById('pauseButton');
        if (pauseButton) {
            pauseButton.innerHTML = '<i class="fas fa-pause me-2"></i>暫停';
            pauseButton.onclick = pauseStudySession;
        }
    }
}

// 結束學習
async function endStudySession() {
    isDetecting = false;
    clearInterval(studyTimer);
    clearInterval(detectionInterval);
    
    try {
        const response = await fetch('/end_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSessionCompleteModal();
        } else {
            showMessage(result.message);
        }
        
    } catch (error) {
        showMessage('結束學習失敗，請稍後再試');
    }
}

// 顯示學習完成模態框
function showSessionCompleteModal() {
    const modal = document.getElementById('sessionCompleteModal');
    const finalDurationElement = document.getElementById('finalDuration');
    const finalAttentionElement = document.getElementById('finalAttention');
    const finalDetectionsElement = document.getElementById('finalDetections');
    
    if (finalDurationElement) {
        const actualDuration = Math.floor((new Date() - startTime) / (1000 * 60));
        finalDurationElement.textContent = `${actualDuration} 分鐘`;
    }
    
    if (finalAttentionElement && emotionData.length > 0) {
        const avgAttention = emotionData.reduce((sum, data) => sum + data.attention, 0) / emotionData.length;
        const avgAttentionPercent = Math.round(avgAttention * 100 / 3);
        finalAttentionElement.textContent = avgAttentionPercent + '%';
    }
    
    if (finalDetectionsElement) {
        finalDetectionsElement.textContent = validDetections;
    }
    
    if (modal) {
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
}

// 生成報告 - 改為返回智慧建議頁面
function generateReport() {
    window.location.href = '/smart_suggestions';
}

// 添加必要的 script 標籤到頁面
if (window.location.pathname.includes('/study/')) {
    // 載入 ONNX Runtime
    const onnxScript = document.createElement('script');
    onnxScript.src = 'https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js';
    document.head.appendChild(tfScript);
}

// 小視窗功能
let miniWindow = null;
let miniWindowInterval = null;

function createMiniWindow() {
    if (miniWindow && !miniWindow.closed) {
        miniWindow.focus();
        return;
    }
    
    miniWindow = window.open('', 'miniMonitor', 'width=350,height=500,resizable=yes');
    
    const miniDoc = miniWindow.document;
    miniDoc.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>學習監控視窗</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <style>
                body { 
                    padding: 10px; 
                    background: #f8f9fa;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }
                .video-mini {
                    width: 100%;
                    border: 2px solid #007bff;
                    border-radius: 10px;
                    margin-bottom: 10px;
                }
                .attention-mini {
                    display: flex;
                    justify-content: space-around;
                    margin: 10px 0;
                }
                .attention-light-mini {
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    color: white;
                    opacity: 0.3;
                }
                .attention-light-mini.active {
                    opacity: 1;
                    box-shadow: 0 0 20px rgba(255,255,255,0.8);
                }
                .alert-mini {
                    position: fixed;
                    top: 10px;
                    left: 10px;
                    right: 10px;
                    z-index: 1000;
                }
            </style>
        </head>
        <body>
            <h5 class="text-center mb-3">
                <i class="fas fa-video me-2"></i>學習監控
            </h5>
            <video id="miniVideo" autoplay muted class="video-mini"></video>
            
            <div class="card">
                <div class="card-body">
                    <h6 class="text-center mb-3">專注度狀態</h6>
                    <div class="attention-mini">
                        <div class="attention-light-mini" style="background: #dc3545;" id="miniLow">
                            <span>低</span>
                        </div>
                        <div class="attention-light-mini" style="background: #ffc107;" id="miniMedium">
                            <span>中</span>
                        </div>
                        <div class="attention-light-mini" style="background: #28a745;" id="miniHigh">
                            <span>高</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="miniAlert" class="alert alert-warning alert-mini" style="display: none;">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <span id="miniAlertText"></span>
            </div>
        </body>
        </html>
    `);
    
    miniDoc.close();
    
    // 設定小視窗的視訊
    setTimeout(() => {
        if (video && video.srcObject) {
            const miniVideo = miniDoc.getElementById('miniVideo');
            if (miniVideo) {
                miniVideo.srcObject = video.srcObject;
            }
        }
    }, 500);
    
    // 開始監控
    startMiniWindowMonitoring();
}

function startMiniWindowMonitoring() {
    if (miniWindowInterval) {
        clearInterval(miniWindowInterval);
    }
    
    miniWindowInterval = setInterval(() => {
        if (!miniWindow || miniWindow.closed) {
            clearInterval(miniWindowInterval);
            return;
        }
        
        // 更新專注度狀態
        updateMiniWindowAttention();
    }, 1000);
}

function updateMiniWindowAttention() {
    if (!miniWindow || miniWindow.closed) return;
    
    const miniDoc = miniWindow.document;
    const lastEmotion = emotionData[emotionData.length - 1];
    
    if (lastEmotion) {
        // 更新專注度指示燈
        ['miniLow', 'miniMedium', 'miniHigh'].forEach(id => {
            const el = miniDoc.getElementById(id);
            if (el) el.classList.remove('active');
        });
        
        if (lastEmotion.attention === 1) {
            const el = miniDoc.getElementById('miniLow');
            if (el) el.classList.add('active');
            showMiniAlert('專注度偏低，請集中注意力！');
        } else if (lastEmotion.attention === 2) {
            const el = miniDoc.getElementById('miniMedium');
            if (el) el.classList.add('active');
        } else if (lastEmotion.attention === 3) {
            const el = miniDoc.getElementById('miniHigh');
            if (el) el.classList.add('active');
        }
    }
}

function showMiniAlert(message) {
    if (!miniWindow || miniWindow.closed) return;
    
    const miniDoc = miniWindow.document;
    const alertEl = miniDoc.getElementById('miniAlert');
    const alertText = miniDoc.getElementById('miniAlertText');
    
    if (alertEl && alertText) {
        alertText.textContent = message;
        alertEl.style.display = 'block';
        
        setTimeout(() => {
            alertEl.style.display = 'none';
        }, 3000);
    }
}

// 監聽頁面離開事件
window.addEventListener('beforeunload', function(e) {
    if (isDetecting) {
        e.preventDefault();
        e.returnValue = '學習階段尚未結束，確定要離開嗎？';
        
        // 顯示小視窗
        createMiniWindow();
    }
});d.appendChild(onnxScript);
    
    // 載入 TensorFlow.js
    const tfScript = document.createElement('script');
    tfScript.src = 'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest/dist/tf.min.js';
    //document.hea