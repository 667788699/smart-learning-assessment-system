// static/script.js
// 全域變數
let video, canvas, ctx;
let faceDetectionModel = null;
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
function initStudyPage() {
    initCamera();
    initStudyControls();
    loadModels();
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
                window.location.href = '/dashboard';
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
                width: 300,
                height: 300,
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

// 載入 AI 模型（模擬）
async function loadModels() {
    try {
        // 在實際實作中，這裡會載入真正的 CNN 模型
        // 現在我們使用模擬的模型
        console.log('正在載入情緒辨識模型...');
        
        // 模擬載入時間
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        faceDetectionModel = { loaded: true };
        emotionModel = { loaded: true };
        
        console.log('模型載入完成');
        updateCameraStatus('AI 模型已就緒，可以開始學習', 'success');
        
    } catch (error) {
        console.error('模型載入失敗:', error);
        updateCameraStatus('AI 模型載入失敗', 'error');
    }
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
    }, 5000); // 每5秒檢測一次
}

// 人臉檢測和情緒辨識
async function detectFaceAndEmotion() {
    try {
        // 將影片畫面繪製到 canvas
        ctx.drawImage(video, 0, 0, 300, 300);
        
        // 模擬人臉檢測和情緒辨識
        const detectionResult = simulateDetection();
        
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

// 模擬檢測結果
function simulateDetection() {
    detectionCount++;
    
    // 模擬各種情況
    const rand = Math.random();
    
    if (rand < 0.05) {
        return { error: '未檢測到人臉，請確保臉部在攝影機範圍內' };
    }
    
    if (rand < 0.1) {
        return { error: '檢測到多人，請確保只有一人在攝影機前' };
    }
    
    validDetections++;
    
    // 模擬情緒和專注度檢測結果
    const emotions = ['happy', 'neutral', 'focused', 'confused', 'tired', 'excited'];
    const emotion = emotions[Math.floor(Math.random() * emotions.length)];
    
    let attention;
    if (emotion === 'focused' || emotion === 'happy') {
        attention = Math.random() < 0.7 ? 3 : 2; // 高專注度
    } else if (emotion === 'neutral' || emotion === 'excited') {
        attention = Math.random() < 0.6 ? 2 : (Math.random() < 0.5 ? 1 : 3); // 中等專注度
    } else {
        attention = Math.random() < 0.8 ? 1 : 2; // 低專注度
    }
    
    return {
        emotion: emotion,
        attention: attention,
        confidence: 0.7 + Math.random() * 0.3 // 0.7-1.0 的信心度
    };
}

// 顯示檢測警告
function showDetectionWarning(message) {
    const warningElement = document.getElementById('detectionWarning');
    const messageElement = document.getElementById('warningMessage');
    
    if (warningElement && messageElement) {
        messageElement.textContent = message;
        warningElement.style.display = 'block';
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
        avgAttentionElement.textContent = avgAttention.toFixed(1);
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
        finalAttentionElement.textContent = avgAttention.toFixed(1);
    }
    
    if (finalDetectionsElement) {
        finalDetectionsElement.textContent = validDetections;
    }
    
    if (modal) {
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
}

// 生成報告
function generateReport() {
    if (currentSessionId) {
        window.open(`/generate_report/${currentSessionId}`, '_blank');
    } else {
        showMessage('無法生成報告，請重新開始學習');
    }
}

// CSS 動畫和樣式（插入到頁面中）
const style = document.createElement('style');
style.textContent = `
    .subject-card {
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
    }
    
    .subject-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    
    .attention-indicator {
        display: flex;
        justify-content: space-around;
        align-items: center;
        margin: 20px 0;
    }
    
    .attention-light {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
        transition: all 0.3s ease;
        opacity: 0.3;
    }
    
    .attention-light:nth-child(1) {
        background-color: #dc3545; /* 紅色 - 低專注 */
    }
    
    .attention-light:nth-child(2) {
        background-color: #ffc107; /* 黃色 - 中等專注 */
    }
    
    .attention-light:nth-child(3) {
        background-color: #28a745; /* 綠色 - 高專注 */
    }
    
    .attention-light.active {
        opacity: 1;
        box-shadow: 0 0 20px rgba(255,255,255,0.8);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    
    .video-container {
        position: relative;
        display: inline-block;
        border: 3px solid #007bff;
        border-radius: 10px;
        overflow: hidden;
    }
    
    .video-container video {
        display: block;
        border-radius: 7px;
    }
    
    .hero-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        min-height: 60vh;
        display: flex;
        align-items: center;
    }
    
    .card {
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .btn {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }
    
    .progress-bar {
        transition: width 1s ease-in-out;
    }
    
    .alert {
        border-radius: 8px;
        border: none;
    }
    
    .navbar-brand {
        font-weight: bold;
        font-size: 1.2rem;
    }
    
    .modal-content {
        border-radius: 12px;
        border: none;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    
    .table {
        border-radius: 8px;
        overflow: hidden;
    }
    
    .badge {
        font-size: 0.9rem;
        padding: 0.5em 0.8em;
    }
    
    /* 響應式設計 */
    @media (max-width: 768px) {
        .video-container {
            width: 100%;
        }
        
        .video-container video {
            width: 100%;
            height: auto;
        }
        
        .attention-light {
            width: 50px;
            height: 50px;
            font-size: 0.8rem;
        }
        
        .hero-section {
            min-height: 50vh;
            padding: 2rem 0;
        }
        
        .display-4 {
            font-size: 2rem;
        }
    }
    
    /* 載入動畫 */
    .loading {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(255,255,255,.3);
        border-radius: 50%;
        border-top-color: #fff;
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    /* 成功/錯誤訊息樣式 */
    .alert-success {
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
    }
    
    .alert-danger {
        background-color: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
    }
    
    .alert-warning {
        background-color: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
    }
    
    .alert-info {
        background-color: #d1ecf1;
        border-color: #bee5eb;
        color: #0c5460;
    }
`;

document.head.appendChild(style);