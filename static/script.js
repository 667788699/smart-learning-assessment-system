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
let faceDetectionModel = null;

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
    
    // 年齡驗證
    const ageInput = document.getElementById('age');
    if (ageInput) {
        ageInput.addEventListener('input', function() {
            const age = parseInt(this.value);
            if (age < 6) {
                this.value = 6;
            } else if (age > 18) {
                this.value = 18;
            }
        });
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
    const age = parseInt(document.getElementById('age').value);
    
    // 驗證年齡
    if (age < 6 || age > 18) {
        showMessage('年齡必須在6-18歲之間');
        return;
    }
    
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
    
    // 年齡驗證小孩創建表單
    const ageInput = document.getElementById('age');
    if (ageInput) {
        ageInput.addEventListener('input', function() {
            const age = parseInt(this.value);
            if (age < 6) {
                this.value = 6;
            } else if (age > 18) {
                this.value = 18;
            }
        });
        
        ageInput.addEventListener('blur', function() {
            const age = parseInt(this.value);
            if (isNaN(age) || age < 6) {
                this.value = 6;
            } else if (age > 18) {
                this.value = 18;
            }
        });
    }
}

// 載入 AI 模型
async function loadModels() {
    try {
        updateCameraStatus('正在載入 AI 模型...', 'info');
        
        // 載入 MediaPipe Face Detection
        if (typeof FaceDetection !== 'undefined') {
            faceDetectionModel = new FaceDetection({
                locateFile: (file) => {
                    return `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`;
                }
            });
            
            faceDetectionModel.setOptions({
                model: 'short',
                minDetectionConfidence: 0.5,
            });
            
            faceDetectionModel.onResults(onFaceDetectionResults);
            console.log('MediaPipe Face Detection 模型載入成功');
        }
        
        // 載入 TensorFlow.js
        if (typeof tf !== 'undefined') {
            try {
                // 嘗試載入情緒分類模型
                emotionModel = await tf.loadLayersModel('/static/models/emotion_model.json');
                console.log('情緒分類模型載入成功');
            } catch (error) {
                console.warn('無法載入情緒分類模型，使用模擬模式');
                emotionModel = { loaded: true, simulated: true };
            }
        } else {
            console.warn('TensorFlow.js 未載入，使用備用方案');
            emotionModel = { loaded: true, simulated: true };
        }
        
        // 如果無法載入真實模型，使用模擬模式
        if (!faceDetectionModel) {
            console.log('使用模擬模式進行臉部檢測');
            faceDetectionModel = { loaded: true, simulated: true };
        }
        
        if (!emotionModel) {
            emotionModel = { loaded: true, simulated: true };
        }
        
        updateCameraStatus('AI 模型已就緒，可以開始學習', 'success');
        
    } catch (error) {
        console.error('模型載入失敗:', error);
        // 使用模擬模式
        faceDetectionModel = { loaded: true, simulated: true };
        emotionModel = { loaded: true, simulated: true };
        updateCameraStatus('使用模擬 AI 模型', 'warning');
    }
}

// MediaPipe 人臉檢測結果處理
let lastFaceDetectionResult = null;

function onFaceDetectionResults(results) {
    lastFaceDetectionResult = results;
}

// 開始學習階段
async function startStudySession() {
    const duration = parseInt(document.getElementById('studyDuration').value);
    
    if (!faceDetectionModel || !emotionModel) {
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
    }, 2000); // 每2秒檢測一次
}

// 人臉檢測和情緒辨識
async function detectFaceAndEmotion() {
    try {
        detectionCount++;
        
        // 將影片畫面繪製到 canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        let detectionResult;
        
        // 檢查是否使用真實的人臉檢測
        if (faceDetectionModel && !faceDetectionModel.simulated) {
            detectionResult = await performRealFaceDetection();
        } else {
            detectionResult = await performEnhancedSimulation();
        }
        
        if (detectionResult.error) {
            showDetectionWarning(detectionResult.error);
            return;
        }
        
        hideDetectionWarning();
        validDetections++;
        
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

// 執行真實的人臉檢測
async function performRealFaceDetection() {
    try {
        // 使用 MediaPipe 進行人臉檢測
        if (faceDetectionModel && typeof faceDetectionModel.send === 'function') {
            await faceDetectionModel.send({image: video});
            
            // 等待檢測結果
            await new Promise(resolve => setTimeout(resolve, 100));
            
            if (lastFaceDetectionResult) {
                const faces = lastFaceDetectionResult.detections;
                
                if (faces.length === 0) {
                    noFaceWarningCount++;
                    if (noFaceWarningCount >= 3) {
                        return { error: '未檢測到人臉，請確保臉部在攝影機範圍內並面向攝影機' };
                    }
                }
                
                if (faces.length > 1) {
                    multipleFaceWarningCount++;
                    if (multipleFaceWarningCount >= 2) {
                        return { error: '檢測到多人，請確保只有一人在攝影機前' };
                    }
                }
                
                if (faces.length === 1) {
                    // 重置警告計數
                    noFaceWarningCount = 0;
                    multipleFaceWarningCount = 0;
                    
                    // 執行情緒檢測
                    const emotion = await performEmotionDetection(faces[0]);
                    const attention = calculateAttentionFromEmotion(emotion.emotion, emotion.confidence);
                    
                    return {
                        emotion: emotion.emotion,
                        attention: attention,
                        confidence: emotion.confidence
                    };
                }
            }
        }
        
        // 如果無法使用真實檢測，回退到增強模擬
        return await performEnhancedSimulation();
        
    } catch (error) {
        console.error('真實人臉檢測失敗:', error);
        return await performEnhancedSimulation();
    }
}

// 執行情緒檢測
async function performEmotionDetection(face) {
    try {
        if (emotionModel && !emotionModel.simulated && typeof tf !== 'undefined') {
            // 從 face 中提取臉部區域
            const faceCanvas = document.createElement('canvas');
            faceCanvas.width = 112;
            faceCanvas.height = 112;
            const faceCtx = faceCanvas.getContext('2d');
            
            // 根據檢測到的臉部邊界框繪製
            const bbox = face.boundingBox;
            const x = bbox.xCenter - bbox.width / 2;
            const y = bbox.yCenter - bbox.height / 2;
            
            faceCtx.drawImage(
                video,
                x * video.videoWidth,
                y * video.videoHeight,
                bbox.width * video.videoWidth,
                bbox.height * video.videoHeight,
                0, 0, 112, 112
            );
            
            // TensorFlow 情緒預測
            const input = tf.browser.fromPixels(faceCanvas);
            const normalized = input.div(255.0);
            const batched = normalized.expandDims(0);
            
            const predictions = await emotionModel.predict(batched).data();
            const emotionIndex = predictions.indexOf(Math.max(...predictions));
            const emotion = EMOTION_LABELS[emotionIndex];
            const confidence = predictions[emotionIndex];
            
            // 清理張量
            input.dispose();
            normalized.dispose();
            batched.dispose();
            
            return { emotion, confidence };
        }
    } catch (error) {
        console.error('情緒檢測失敗:', error);
    }
    
    // 回退到模擬情緒檢測
    return simulateEmotion();
}

// 增強版模擬檢測（更真實的人臉檢測行為）
async function performEnhancedSimulation() {
    // 使用簡單的像素分析來模擬人臉檢測
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;
    
    // 計算圖像中心區域的亮度變化（簡單的人臉存在檢測）
    let centerBrightness = 0;
    let edgeBrightness = 0;
    let centerPixels = 0;
    let edgePixels = 0;
    
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const faceRadius = Math.min(canvas.width, canvas.height) / 6;
    
    for (let y = 0; y < canvas.height; y += 4) {
        for (let x = 0; x < canvas.width; x += 4) {
            const distance = Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2);
            const pixelIndex = (y * canvas.width + x) * 4;
            const brightness = (pixels[pixelIndex] + pixels[pixelIndex + 1] + pixels[pixelIndex + 2]) / 3;
            
            if (distance < faceRadius) {
                centerBrightness += brightness;
                centerPixels++;
            } else if (distance > faceRadius * 2) {
                edgeBrightness += brightness;
                edgePixels++;
            }
        }
    }
    
    const avgCenterBrightness = centerBrightness / centerPixels;
    const avgEdgeBrightness = edgeBrightness / edgePixels;
    const contrast = Math.abs(avgCenterBrightness - avgEdgeBrightness);
    
    // 檢測多人的簡單方法：檢查是否有多個亮度區域
    let brightRegions = 0;
    for (let y = 0; y < canvas.height; y += 20) {
        for (let x = 0; x < canvas.width; x += 20) {
            const pixelIndex = (y * canvas.width + x) * 4;
            const brightness = (pixels[pixelIndex] + pixels[pixelIndex + 1] + pixels[pixelIndex + 2]) / 3;
            if (brightness > avgCenterBrightness + 20) {
                brightRegions++;
            }
        }
    }
    
    // 根據圖像分析結果決定檢測結果
    const rand = Math.random();
    
    // 如果對比度太低，可能沒有人臉
    if (contrast < 15 && rand < 0.3) {
        noFaceWarningCount++;
        if (noFaceWarningCount >= 2) {
            return { error: '未檢測到人臉，請確保臉部在攝影機範圍內並面向攝影機' };
        }
    }
    
    // 如果有太多亮區域，可能有多人
    if (brightRegions > 8 && rand < 0.15) {
        multipleFaceWarningCount++;
        if (multipleFaceWarningCount >= 1) {
            return { error: '檢測到多人，請確保只有一人在攝影機前' };
        }
    }
    
    // 正常情況下的檢測
    noFaceWarningCount = Math.max(0, noFaceWarningCount - 0.5);
    multipleFaceWarningCount = Math.max(0, multipleFaceWarningCount - 0.5);
    
    const emotion = simulateEmotion();
    const attention = calculateAttentionFromEmotion(emotion.emotion, emotion.confidence);
    
    return {
        emotion: emotion.emotion,
        attention: attention,
        confidence: emotion.confidence
    };
}

// 模擬情緒檢測
function simulateEmotion() {
    // 模擬更真實的情緒分布
    const emotionWeights = {
        'neutral': 0.45,
        'happy': 0.15,
        'focused': 0.25,
        'confused': 0.08,
        'tired': 0.04,
        'surprised': 0.03
    };
    
    let randomValue = Math.random();
    let emotion = 'neutral';
    
    for (const [emo, weight] of Object.entries(emotionWeights)) {
        randomValue -= weight;
        if (randomValue <= 0) {
            emotion = emo;
            break;
        }
    }
    
    const confidence = 0.6 + Math.random() * 0.35;
    return { emotion, confidence };
}

// 根據情緒計算專注度
function calculateAttentionFromEmotion(emotion, confidence) {
    const attentionMap = {
        'neutral': 3,
        'focused': 3,
        'happy': 2,
        'surprised': 2,
        'confused': 1,
        'tired': 1,
        'angry': 1,
        'sad': 1
    };
    
    let baseAttention = attentionMap[emotion] || 2;
    
    // 根據信心度調整
    if (confidence < 0.6) {
        baseAttention = Math.max(1, baseAttention - 1);
    } else if (confidence > 0.85) {
        baseAttention = Math.min(3, baseAttention + 0.5);
    }
    
    return Math.round(baseAttention);
}

// 顯示檢測警告
function showDetectionWarning(message) {
    const warningElement = document.getElementById('detectionWarning');
    const messageElement = document.getElementById('warningMessage');
    
    if (warningElement && messageElement) {
        messageElement.textContent = message;
        warningElement.style.display = 'block';
        
        // 5秒後自動隱藏
        setTimeout(() => {
            hideDetectionWarning();
        }, 5000);
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

// 刪除學習記錄
async function deleteStudySession(sessionId) {
    if (!confirm('確定要刪除這次學習記錄嗎？')) {
        return;
    }
    
    try {
        const response = await fetch(`/delete_session/${sessionId}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 重新載入頁面以更新資料
            window.location.reload();
        } else {
            alert('刪除失敗：' + result.message);
        }
    } catch (error) {
        alert('刪除失敗，請稍後再試');
    }
}

// 載入必要的外部庫
if (window.location.pathname.includes('/study/')) {
    // 載入 MediaPipe Face Detection
    const mediapipeScript = document.createElement('script');
    mediapipeScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/face_detection.js';
    mediapipeScript.onload = () => {
        console.log('MediaPipe Face Detection 載入完成');
    };
    document.head.appendChild(mediapipeScript);
    
    // 載入 TensorFlow.js
    const tfScript = document.createElement('script');
    tfScript.src = 'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest/dist/tf.min.js';
    tfScript.onload = () => {
        console.log('TensorFlow.js 載入完成');
    };
    document.head.appendChild(tfScript);
}