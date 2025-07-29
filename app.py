from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import json
import os
import sqlite3
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learning_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# 資料庫模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    study_sessions = db.relationship('StudySession', backref='user', lazy=True)

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    avg_attention = db.Column(db.Float)
    avg_emotion_score = db.Column(db.Float)
    emotion_data = db.relationship('EmotionData', backref='study_session', lazy=True)

class EmotionData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('study_session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    emotion = db.Column(db.String(20))
    attention_level = db.Column(db.Integer)  # 1-低, 2-中, 3-高
    confidence = db.Column(db.Float)

# 學科分類配置
SUBJECTS = {
    'math': '數學',
    'science': '自然科學',
    'language': '語言文學',
    'social': '社會科學',
    'art': '藝術創作',
    'programming': '程式設計'
}

@app.route('/')
def index():
    """首頁路由"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """註冊功能"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # 檢查使用者是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': '使用者名稱已存在'})
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': '電子郵件已註冊'})
        
        # 建立新使用者
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '註冊成功'})
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登入功能"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({'success': True, 'message': '登入成功'})
        else:
            return jsonify({'success': False, 'message': '使用者名稱或密碼錯誤'})
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """使用者儀表板 - 學科選擇頁面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # 獲取使用者歷史學習記錄統計 - 修正變數名稱避免與 session 衝突
    user_study_sessions = StudySession.query.filter_by(user_id=user_id).all()
    subject_stats = {}
    
    for study_record in user_study_sessions:
        if study_record.subject not in subject_stats:
            subject_stats[study_record.subject] = {
                'count': 0,
                'total_time': 0,
                'avg_attention': 0
            }
        subject_stats[study_record.subject]['count'] += 1
        subject_stats[study_record.subject]['total_time'] += study_record.duration_minutes
        if study_record.avg_attention:
            subject_stats[study_record.subject]['avg_attention'] += study_record.avg_attention
    
    # 計算平均專注度
    for subject in subject_stats:
        if subject_stats[subject]['count'] > 0:
            subject_stats[subject]['avg_attention'] /= subject_stats[subject]['count']
    
    return render_template('dashboard.html', 
                         subjects=SUBJECTS, 
                         stats=subject_stats,
                         user=user)

@app.route('/study/<subject>')
def study_session(subject):
    """學習檢測頁面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if subject not in SUBJECTS:
        return redirect(url_for('dashboard'))
    
    return render_template('study.html', 
                         subject=subject, 
                         subject_name=SUBJECTS[subject])

@app.route('/start_session', methods=['POST'])
def start_session():
    """開始學習階段"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '請先登入'})
    
    data = request.get_json()
    subject = data.get('subject')
    duration = data.get('duration', 30)  # 預設30分鐘
    
    # 建立新的學習階段記錄
    new_study_session = StudySession(
        user_id=session['user_id'],
        subject=subject,
        duration_minutes=duration,
        start_time=datetime.utcnow()
    )
    db.session.add(new_study_session)
    db.session.commit()
    
    session['current_session_id'] = new_study_session.id
    
    return jsonify({'success': True, 'session_id': new_study_session.id})

@app.route('/record_emotion', methods=['POST'])
def record_emotion():
    """記錄情緒檢測數據"""
    if 'current_session_id' not in session:
        return jsonify({'success': False, 'message': '沒有活躍的學習階段'})
    
    data = request.get_json()
    emotion = data.get('emotion')
    attention_level = data.get('attention_level')
    confidence = data.get('confidence')
    
    # 儲存情緒數據
    emotion_data = EmotionData(
        session_id=session['current_session_id'],
        emotion=emotion,
        attention_level=attention_level,
        confidence=confidence,
        timestamp=datetime.utcnow()
    )
    db.session.add(emotion_data)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/end_session', methods=['POST'])
def end_session():
    """結束學習階段"""
    if 'current_session_id' not in session:
        return jsonify({'success': False, 'message': '沒有活躍的學習階段'})
    
    session_id = session['current_session_id']
    current_study_session = StudySession.query.get(session_id)
    
    if current_study_session:
        current_study_session.end_time = datetime.utcnow()
        
        # 計算平均專注度和情緒分數
        emotion_records = EmotionData.query.filter_by(session_id=session_id).all()
        
        if emotion_records:
            avg_attention = sum(record.attention_level for record in emotion_records) / len(emotion_records)
            avg_emotion = sum(record.confidence for record in emotion_records) / len(emotion_records)
            
            current_study_session.avg_attention = avg_attention
            current_study_session.avg_emotion_score = avg_emotion
        
        db.session.commit()
        
        # 清除當前階段
        session.pop('current_session_id', None)
        
        return jsonify({'success': True, 'session_id': session_id})
    
    return jsonify({'success': False, 'message': '找不到學習階段'})

@app.route('/generate_report/<int:session_id>')
def generate_report(session_id):
    """生成PDF學習報告"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    target_study_session = StudySession.query.get_or_404(session_id)
    
    # 確認是當前使用者的階段
    if target_study_session.user_id != session['user_id']:
        return redirect(url_for('dashboard'))
    
    # 生成PDF報告
    pdf_path = create_detailed_report(target_study_session)
    
    return send_file(pdf_path, as_attachment=True, 
                    download_name=f'學習報告_{target_study_session.subject}_{datetime.now().strftime("%Y%m%d")}.pdf')

def create_detailed_report(study_session):
    """建立詳細的PDF報告"""
    filename = f'report_{study_session.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    filepath = os.path.join('reports', filename)
    
    # 確保reports目錄存在
    os.makedirs('reports', exist_ok=True)
    
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # 標題
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.blue,
        alignment=1,  # 置中
        spaceAfter=30
    )
    
    story.append(Paragraph('智慧學習評估報告', title_style))
    story.append(Spacer(1, 20))
    
    # 基本資訊
    user = User.query.get(study_session.user_id)
    basic_info = [
        ['學習者', user.username],
        ['學科', SUBJECTS.get(study_session.subject, study_session.subject)],
        ['學習時間', f"{study_session.duration_minutes} 分鐘"],
        ['開始時間', study_session.start_time.strftime('%Y-%m-%d %H:%M:%S')],
        ['結束時間', study_session.end_time.strftime('%Y-%m-%d %H:%M:%S') if study_session.end_time else '進行中'],
        ['平均專注度', f"{study_session.avg_attention:.2f}" if study_session.avg_attention else "計算中"]
    ]
    
    info_table = Table(basic_info, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 30))
    
    # 專注度分析圖表
    emotion_data = EmotionData.query.filter_by(session_id=study_session.id).all()
    
    if emotion_data:
        # 生成專注度趨勢圖
        attention_chart_path = create_attention_chart(emotion_data, study_session.id)
        if attention_chart_path:
            story.append(Paragraph('專注度變化趨勢', styles['Heading2']))
            story.append(Image(attention_chart_path, width=6*inch, height=4*inch))
            story.append(Spacer(1, 20))
        
        # 情緒分布圖
        emotion_chart_path = create_emotion_distribution_chart(emotion_data, study_session.id)
        if emotion_chart_path:
            story.append(Paragraph('情緒狀態分布', styles['Heading2']))
            story.append(Image(emotion_chart_path, width=6*inch, height=4*inch))
            story.append(Spacer(1, 20))
    
    # 個人化建議
    recommendations = generate_personalized_recommendations(user, study_session)
    story.append(Paragraph('個人化學習建議', styles['Heading2']))
    
    for recommendation in recommendations:
        story.append(Paragraph(f"• {recommendation}", styles['Normal']))
        story.append(Spacer(1, 10))
    
    # 歷史表現比較
    historical_comparison = get_historical_comparison(user, study_session.subject)
    if historical_comparison:
        story.append(Spacer(1, 20))
        story.append(Paragraph('歷史表現比較', styles['Heading2']))
        story.append(Paragraph(historical_comparison, styles['Normal']))
    
    doc.build(story)
    return filepath

def create_attention_chart(emotion_data, session_id):
    """建立專注度趨勢圖"""
    try:
        times = [data.timestamp for data in emotion_data]
        attention_levels = [data.attention_level for data in emotion_data]
        
        plt.figure(figsize=(10, 6))
        plt.plot(times, attention_levels, 'b-', linewidth=2, markersize=4, marker='o')
        plt.title('專注度變化趨勢', fontsize=16, fontweight='bold')
        plt.xlabel('時間', fontsize=12)
        plt.ylabel('專注度等級', fontsize=12)
        plt.ylim(0, 4)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        chart_path = f'reports/attention_chart_{session_id}.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    except Exception as e:
        print(f"建立專注度圖表時發生錯誤: {e}")
        return None

def create_emotion_distribution_chart(emotion_data, session_id):
    """建立情緒分布圖"""
    try:
        emotions = [data.emotion for data in emotion_data if data.emotion]
        emotion_counts = {}
        
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        if not emotion_counts:
            return None
        
        plt.figure(figsize=(10, 6))
        plt.bar(emotion_counts.keys(), emotion_counts.values(), 
               color=['skyblue', 'lightgreen', 'salmon', 'gold', 'plum', 'orange'])
        plt.title('情緒狀態分布', fontsize=16, fontweight='bold')
        plt.xlabel('情緒類型', fontsize=12)
        plt.ylabel('出現次數', fontsize=12)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        chart_path = f'reports/emotion_chart_{session_id}.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_path
    except Exception as e:
        print(f"建立情緒分布圖表時發生錯誤: {e}")
        return None

def generate_personalized_recommendations(user, current_session):
    """生成個人化學習建議"""
    recommendations = []
    
    # 獲取使用者歷史數據
    all_study_sessions = StudySession.query.filter_by(user_id=user.id).all()
    subject_study_sessions = [s for s in all_study_sessions if s.subject == current_session.subject]
    
    # 基於專注度的建議
    if current_session.avg_attention:
        if current_session.avg_attention < 2:
            recommendations.append("建議在學習前進行10分鐘的冥想或深呼吸練習，有助於提升專注力")
            recommendations.append("考慮將學習時間縮短為20-25分鐘一個段落，中間休息5分鐘")
        elif current_session.avg_attention > 2.5:
            recommendations.append("您在這個學科表現出色的專注力！建議可以嘗試更具挑戰性的學習內容")
    
    # 基於學習次數的建議
    if len(subject_study_sessions) >= 5:
        avg_attention_trend = [s.avg_attention for s in subject_study_sessions[-5:] if s.avg_attention]
        if len(avg_attention_trend) >= 3:
            if avg_attention_trend[-1] > avg_attention_trend[0]:
                recommendations.append(f"太棒了！您在{SUBJECTS[current_session.subject]}的專注度呈現上升趨勢，持續保持！")
            else:
                recommendations.append(f"建議調整{SUBJECTS[current_session.subject]}的學習方式，嘗試不同的學習策略")
    
    # 基於時間段的建議
    study_hour = current_session.start_time.hour
    if study_hour < 9:
        recommendations.append("早晨學習很棒！大腦在這個時間段通常最為清晰")
    elif study_hour > 21:
        recommendations.append("建議避免太晚學習，可能會影響睡眠品質和隔天的學習效果")
    
    # 跨學科比較建議
    if len(all_study_sessions) >= 3:
        subject_avg = {}
        for study_record in all_study_sessions:
            if study_record.avg_attention and study_record.subject != current_session.subject:
                if study_record.subject not in subject_avg:
                    subject_avg[study_record.subject] = []
                subject_avg[study_record.subject].append(study_record.avg_attention)
        
        best_subject = None
        best_avg = 0
        for subject, attentions in subject_avg.items():
            avg = sum(attentions) / len(attentions)
            if avg > best_avg:
                best_avg = avg
                best_subject = subject
        
        if best_subject and best_avg > (current_session.avg_attention or 0) + 0.5:
            recommendations.append(f"您在{SUBJECTS[best_subject]}表現最佳，可以考慮將該學科的學習方法應用到其他科目")
    
    if not recommendations:
        recommendations.append("繼續保持良好的學習習慣，定期檢視您的學習進度！")
    
    return recommendations

def get_historical_comparison(user, subject):
    """獲取歷史表現比較"""
    historical_sessions = StudySession.query.filter_by(user_id=user.id, subject=subject).order_by(StudySession.start_time).all()
    
    if len(historical_sessions) < 2:
        return "這是您在此學科的第一次記錄，期待看到您的進步！"
    
    recent_sessions = [s for s in historical_sessions[-3:] if s.avg_attention]
    early_sessions = [s for s in historical_sessions[:3] if s.avg_attention]
    
    if not recent_sessions or not early_sessions:
        return "數據不足以進行比較分析"
    
    recent_avg = sum(s.avg_attention for s in recent_sessions) / len(recent_sessions)
    early_avg = sum(s.avg_attention for s in early_sessions) / len(early_sessions)
    
    if recent_avg > early_avg:
        improvement = ((recent_avg - early_avg) / early_avg) * 100
        return f"太棒了！相比初期，您的專注度提升了 {improvement:.1f}%"
    else:
        decline = ((early_avg - recent_avg) / early_avg) * 100
        return f"最近的專注度相比初期下降了 {decline:.1f}%，建議調整學習策略"

@app.route('/logout')
def logout():
    """登出功能"""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))