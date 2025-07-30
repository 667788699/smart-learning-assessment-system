from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import json
import os
import sqlite3
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# 嘗試導入 matplotlib 和 numpy，如果失敗則使用替代方案
try:
   import matplotlib
   matplotlib.use('Agg')  # 使用非互動式後端
   import matplotlib.pyplot as plt
   import numpy as np
   from matplotlib.font_manager import FontProperties
   # 設定中文字體
   plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
   plt.rcParams['axes.unicode_minus'] = False
   CHARTS_AVAILABLE = True
except ImportError:
   CHARTS_AVAILABLE = False
   print("Charts功能暫時無法使用，將生成純文字報告")

from io import BytesIO
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learning_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# 註冊中文字體用於 PDF
try:
    # 嘗試註冊 CID 字體
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
except:
    try:
        # 嘗試使用系統字體
        pdfmetrics.registerFont(TTFont('SimSun', 'simsun.ttc'))
    except:
        # 如果找不到中文字體，使用內建字體
        pass

# 資料庫模型
class User(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(80), unique=True, nullable=False)
   email = db.Column(db.String(120), unique=True, nullable=False)
   password_hash = db.Column(db.String(60), nullable=False)
   created_at = db.Column(db.DateTime, default=datetime.utcnow)
   children = db.relationship('Child', backref='user', lazy=True, cascade='all, delete-orphan')

class Child(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
   nickname = db.Column(db.String(80), nullable=False)
   gender = db.Column(db.String(10), nullable=False)  # male/female
   age = db.Column(db.Integer, nullable=False)
   education_stage = db.Column(db.String(20), nullable=False)  # elementary/middle/high
   created_at = db.Column(db.DateTime, default=datetime.utcnow)
   study_sessions = db.relationship('StudySession', backref='child', lazy=True, cascade='all, delete-orphan')

class StudySession(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
   subject = db.Column(db.String(50), nullable=False)
   duration_minutes = db.Column(db.Integer, nullable=False)
   start_time = db.Column(db.DateTime, default=datetime.utcnow)
   end_time = db.Column(db.DateTime)
   avg_attention = db.Column(db.Float)
   avg_emotion_score = db.Column(db.Float)
   emotion_data = db.relationship('EmotionData', backref='study_session', lazy=True, cascade='all, delete-orphan')

class EmotionData(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   session_id = db.Column(db.Integer, db.ForeignKey('study_session.id'), nullable=False)
   timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   emotion = db.Column(db.String(20))
   attention_level = db.Column(db.Integer)  # 1-低, 2-中, 3-高
   confidence = db.Column(db.Float)

# 學科分類配置 - 更新程式設計為電腦科學
SUBJECTS = {
   'math': '數學',
   'science': '自然科學',
   'language': '語言文學',
   'social': '社會科學',
   'art': '藝術創作',
   'cs': '電腦科學'  # 原本的 programming 改為 cs
}

# 教育階段中文對照
EDUCATION_STAGES = {
   'elementary': '國小',
   'middle': '國中',
   'high': '高中'
}

# 性別中文對照
GENDERS = {
   'male': '男生',
   'female': '女生'
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

@app.route('/child_selection')
def child_selection():
   """選擇或新增小孩"""
   if 'user_id' not in session:
       return redirect(url_for('login'))
   
   user_id = session['user_id']
   children = Child.query.filter_by(user_id=user_id).all()
   
   return render_template('child_selection.html', children=children)

@app.route('/create_child', methods=['POST'])
def create_child():
   """創建新的小孩檔案"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   data = request.get_json()
   nickname = data.get('nickname')
   gender = data.get('gender')
   age = data.get('age')
   education_stage = data.get('education_stage')
   
   # 檢查是否已達到4個小孩的限制
   existing_children = Child.query.filter_by(user_id=session['user_id']).count()
   if existing_children >= 4:
       return jsonify({'success': False, 'message': '最多只能創建4個小孩檔案'})
   
   # 創建新的小孩檔案
   child = Child(
       user_id=session['user_id'],
       nickname=nickname,
       gender=gender,
       age=int(age),
       education_stage=education_stage
   )
   db.session.add(child)
   db.session.commit()
   
   return jsonify({'success': True, 'child_id': child.id})

@app.route('/select_child/<int:child_id>')
def select_child(child_id):
   """選擇小孩進入學習環境"""
   if 'user_id' not in session:
       return redirect(url_for('login'))
   
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   if not child:
       return redirect(url_for('child_selection'))
   
   session['child_id'] = child.id
   session['child_nickname'] = child.nickname
   
   return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
   """使用者儀表板 - 學科選擇頁面"""
   if 'user_id' not in session or 'child_id' not in session:
       return redirect(url_for('child_selection'))
   
   child_id = session['child_id']
   child = Child.query.get(child_id)
   
   # 獲取小孩的學習記錄統計
   user_study_sessions = StudySession.query.filter_by(child_id=child_id).all()
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
                        child=child)

@app.route('/study/<subject>')
def study_session(subject):
   """學習檢測頁面"""
   if 'user_id' not in session or 'child_id' not in session:
       return redirect(url_for('child_selection'))
   
   if subject not in SUBJECTS:
       return redirect(url_for('dashboard'))
   
   child = Child.query.get(session['child_id'])
   
   return render_template('study.html', 
                        subject=subject, 
                        subject_name=SUBJECTS[subject],
                        child=child)

@app.route('/start_session', methods=['POST'])
def start_session():
   """開始學習階段"""
   if 'user_id' not in session or 'child_id' not in session:
       return jsonify({'success': False, 'message': '請先登入並選擇小孩'})
   
   data = request.get_json()
   subject = data.get('subject')
   duration = data.get('duration', 30)
   
   # 建立新的學習階段記錄
   new_study_session = StudySession(
       child_id=session['child_id'],
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

@app.route('/data_analysis')
def data_analysis():
   """數據分析頁面"""
   if 'user_id' not in session or 'child_id' not in session:
       return redirect(url_for('child_selection'))
   
   child = Child.query.get(session['child_id'])
   study_sessions = StudySession.query.filter_by(child_id=child.id).order_by(StudySession.start_time.desc()).all()
   
   # 準備圖表數據
   chart_data = prepare_chart_data(study_sessions)
   
   return render_template('data_analysis.html', 
                        child=child, 
                        study_sessions=study_sessions,
                        chart_data=chart_data)

@app.route('/smart_suggestions')
def smart_suggestions():
   """智慧建議頁面"""
   if 'user_id' not in session or 'child_id' not in session:
       return redirect(url_for('child_selection'))
   
   child = Child.query.get(session['child_id'])
   study_sessions = StudySession.query.filter_by(child_id=child.id).all()
   
   # 生成個人化建議
   suggestions = generate_comprehensive_suggestions(child, study_sessions)
   
   # 準備視覺化數據
   performance_data = prepare_performance_data(study_sessions)
   
   return render_template('smart_suggestions.html',
                        child=child,
                        suggestions=suggestions,
                        performance_data=performance_data)

@app.route('/generate_report/<int:child_id>')
def generate_report(child_id):
   """生成PDF學習報告 - 從智慧建議頁面"""
   if 'user_id' not in session:
       return redirect(url_for('login'))
   
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   if not child:
       return redirect(url_for('dashboard'))
   
   # 獲取所有學習記錄
   study_sessions = StudySession.query.filter_by(child_id=child.id).all()
   
   # 生成PDF報告
   pdf_path = create_comprehensive_report(child, study_sessions)
   
   return send_file(pdf_path, as_attachment=True, 
                   download_name=f'學習報告_{child.nickname}_{datetime.now().strftime("%Y%m%d")}.pdf')

@app.route('/delete_child/<int:child_id>', methods=['POST'])
def delete_child(child_id):
   """刪除小孩檔案"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   if child:
       db.session.delete(child)
       db.session.commit()
       
       # 如果刪除的是當前選中的小孩，清除session
       if session.get('child_id') == child_id:
           session.pop('child_id', None)
           session.pop('child_nickname', None)
       
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到該小孩檔案'})

@app.route('/reset_learning_history/<int:child_id>', methods=['POST'])
def reset_learning_history(child_id):
   """重置學習歷程"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   if child:
       # 刪除所有學習記錄
       StudySession.query.filter_by(child_id=child_id).delete()
       db.session.commit()
       
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到該小孩檔案'})

@app.route('/delete_account', methods=['POST'])
def delete_account():
   """刪除帳號"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   user = User.query.get(session['user_id'])
   if user:
       db.session.delete(user)
       db.session.commit()
       session.clear()
       
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到該帳號'})

def prepare_chart_data(study_sessions):
   """準備圖表數據"""
   chart_data = {
       'subjects': [],
       'attention_scores': [],
       'study_times': [],
       'dates': [],
       'attention_trend': []
   }
   
   # 按科目統計
   subject_stats = {}
   for session in study_sessions:
       if session.subject not in subject_stats:
           subject_stats[session.subject] = {
               'total_time': 0,
               'avg_attention': 0,
               'count': 0
           }
       subject_stats[session.subject]['total_time'] += session.duration_minutes
       if session.avg_attention:
           subject_stats[session.subject]['avg_attention'] += session.avg_attention
           subject_stats[session.subject]['count'] += 1
   
   # 轉換為圖表格式
   for subject, stats in subject_stats.items():
       chart_data['subjects'].append(SUBJECTS.get(subject, subject))
       chart_data['study_times'].append(stats['total_time'])
       if stats['count'] > 0:
           avg = stats['avg_attention'] / stats['count']
           chart_data['attention_scores'].append(round(avg * 100 / 3))  # 轉換為百分比
       else:
           chart_data['attention_scores'].append(0)
   
   # 專注度趨勢（最近10次）
   recent_sessions = sorted(study_sessions, key=lambda x: x.start_time)[-10:]
   for session in recent_sessions:
       chart_data['dates'].append(session.start_time.strftime('%m/%d'))
       if session.avg_attention:
           chart_data['attention_trend'].append(round(session.avg_attention * 100 / 3))
       else:
           chart_data['attention_trend'].append(0)
   
   return chart_data

def prepare_performance_data(study_sessions):
   """準備表現數據"""
   data = {
       'total_sessions': len(study_sessions),
       'total_hours': sum(s.duration_minutes for s in study_sessions) / 60,
       'avg_attention': 0,
       'best_subject': '',
       'improvement_rate': 0
   }
   
   if study_sessions:
       # 計算平均專注度
       attention_sessions = [s for s in study_sessions if s.avg_attention]
       if attention_sessions:
           data['avg_attention'] = round(sum(s.avg_attention for s in attention_sessions) / len(attention_sessions) * 100 / 3)
       
       # 找出最佳科目
       subject_performance = {}
       for session in study_sessions:
           if session.avg_attention:
               if session.subject not in subject_performance:
                   subject_performance[session.subject] = []
               subject_performance[session.subject].append(session.avg_attention)
       
       if subject_performance:
           best_subject = max(subject_performance.items(), key=lambda x: sum(x[1])/len(x[1]))
           data['best_subject'] = SUBJECTS.get(best_subject[0], best_subject[0])
       
       # 計算進步率
       if len(attention_sessions) >= 5:
           early_avg = sum(s.avg_attention for s in attention_sessions[:3]) / 3
           recent_avg = sum(s.avg_attention for s in attention_sessions[-3:]) / 3
           data['improvement_rate'] = round((recent_avg - early_avg) / early_avg * 100)
   
   return data

def generate_comprehensive_suggestions(child, study_sessions):
   """生成全面的個人化建議"""
   suggestions = {
       'learning_style': [],
       'schedule': [],
       'subject_specific': [],
       'attention_improvement': [],
       'age_appropriate': []
   }
   
   # 基於年齡和教育階段的建議
   if child.education_stage == 'elementary':
       if child.age <= 8:
           suggestions['age_appropriate'].append("建議每次學習時間控制在15-20分鐘，並搭配互動式學習活動")
           suggestions['age_appropriate'].append("可以使用獎勵貼紙或積分制度來增加學習動機")
       else:
           suggestions['age_appropriate'].append("可以逐漸延長學習時間至25-30分鐘，培養專注力")
           suggestions['age_appropriate'].append("鼓勵自主選擇學習主題，提升學習興趣")
   elif child.education_stage == 'middle':
       suggestions['age_appropriate'].append("這個階段的學生需要更多的自主學習空間，建議設定明確的學習目標")
       suggestions['age_appropriate'].append("可以嘗試番茄工作法，25分鐘專注學習，5分鐘休息")
   else:  # high school
       suggestions['age_appropriate'].append("高中生需要更長的專注時間，建議每次學習45-60分鐘")
       suggestions['age_appropriate'].append("重視學習效率，建議使用思維導圖等學習工具")
   
   # 基於性別的建議（謹慎處理，避免刻板印象）
   if child.gender == 'female':
       suggestions['learning_style'].append("研究顯示女生在合作學習環境中表現更好，可以考慮與朋友一起學習")
   else:
       suggestions['learning_style'].append("研究顯示男生在競爭性學習環境中較有動力，可以設定挑戰性目標")
   
   # 基於學習數據的建議
   if study_sessions:
       # 專注度分析
       attention_sessions = [s for s in study_sessions if s.avg_attention]
       if attention_sessions:
           avg_attention = sum(s.avg_attention for s in attention_sessions) / len(attention_sessions)
           
           if avg_attention < 1.5:
               suggestions['attention_improvement'].append("專注度偏低，建議檢查學習環境是否有干擾因素")
               suggestions['attention_improvement'].append("可以嘗試使用白噪音或輕音樂幫助集中注意力")
           elif avg_attention < 2.5:
               suggestions['attention_improvement'].append("專注度中等，建議使用計時器設定專注時段")
               suggestions['attention_improvement'].append("學習前做5分鐘的深呼吸或伸展運動")
           else:
               suggestions['attention_improvement'].append("專注度表現優秀！繼續保持良好的學習習慣")
               suggestions['attention_improvement'].append("可以嘗試更有挑戰性的學習內容")
       
       # 時間規劃建議
       study_hours = {}
       for session in study_sessions:
           hour = session.start_time.hour
           if hour not in study_hours:
               study_hours[hour] = []
           if session.avg_attention:
               study_hours[hour].append(session.avg_attention)
       
       if study_hours:
           best_hour = max(study_hours.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0)
           suggestions['schedule'].append(f"您的孩子在{best_hour[0]}點學習時專注度最高，建議安排重要科目在這個時段")
       
       # 科目建議
       subject_performance = {}
       for session in study_sessions:
           if session.avg_attention:
               if session.subject not in subject_performance:
                   subject_performance[session.subject] = []
               subject_performance[session.subject].append(session.avg_attention)
       
       for subject, performances in subject_performance.items():
           avg_perf = sum(performances) / len(performances)
           subject_name = SUBJECTS.get(subject, subject)
           
           # 根據教育階段和科目給予更具體建議
           if subject == 'math':
               if child.education_stage == 'elementary':
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議使用實物教具和圖像化教學")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以嘗試趣味數學遊戲加深理解")
               elif child.education_stage == 'middle':
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議分解複雜問題為小步驟")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以挑戰奧數題型")
               else:  # high school
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議建立錯題本並定期複習")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以嘗試大學先修課程")
           
           elif subject == 'science':
               if child.education_stage == 'elementary':
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議多做實驗觀察自然現象")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以參加科學營隊")
               elif child.education_stage == 'middle':
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議使用概念圖整理知識")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以參加科展競賽")
               else:
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議加強實驗設計能力")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以閱讀科學期刊文章")
           
           elif subject == 'language':
               if avg_perf < 2:
                   suggestions['subject_specific'].append(f"{subject_name}需要加強，建議每日閱讀30分鐘並寫讀書心得")
               else:
                   suggestions['subject_specific'].append(f"{subject_name}表現良好，可以嘗試創意寫作或參加作文比賽")
           
           elif subject == 'cs':
               if child.education_stage == 'elementary':
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議從Scratch圖像化程式開始")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以學習基礎Python")
               else:
                   if avg_perf < 2:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議先理解邏輯概念再練習編碼")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}表現良好，可以參加程式競賽或開發小專案")
   
   return suggestions

def create_comprehensive_report(child, study_sessions):
   """建立全面的PDF報告"""
   filename = f'report_{child.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
   filepath = os.path.join('reports', filename)
   
   # 確保reports目錄存在
   os.makedirs('reports', exist_ok=True)
   
   doc = SimpleDocTemplate(filepath, pagesize=A4)
   story = []
   
   # 設定樣式
   styles = getSampleStyleSheet()
   
   # 自定義樣式以支援中文
   title_style = ParagraphStyle(
       'ChineseTitle',
       parent=styles['Title'],
       fontName='Helvetica-Bold',
       fontSize=24,
       textColor=colors.HexColor('#2C3E50'),
       alignment=TA_CENTER,
       spaceAfter=30
   )
   
   heading_style = ParagraphStyle(
       'ChineseHeading',
       parent=styles['Heading1'],
       fontName='Helvetica-Bold',
       fontSize=16,
       textColor=colors.HexColor('#34495E'),
       spaceAfter=12
   )
   
   normal_style = ParagraphStyle(
       'ChineseNormal',
       parent=styles['Normal'],
       fontName='Helvetica',
       fontSize=12,
       leading=18
   )
   
   # 標題頁
   story.append(Paragraph('Learning Assessment Report', title_style))
   story.append(Spacer(1, 30))
   
   # 基本資訊表格
   user = User.query.get(child.user_id)
   basic_info = [
       ['Child Name', child.nickname],
       ['Gender', GENDERS.get(child.gender, child.gender)],
       ['Age', str(child.age)],
       ['Education Stage', EDUCATION_STAGES.get(child.education_stage, child.education_stage)],
       ['Report Date', datetime.now().strftime('%Y-%m-%d')],
       ['Total Sessions', str(len(study_sessions))]
   ]
   
   info_table = Table(basic_info, colWidths=[2.5*inch, 3.5*inch])
   info_table.setStyle(TableStyle([
       ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ECF0F1')),
       ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
       ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
       ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
       ('FONTSIZE', (0, 0), (-1, -1), 12),
       ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
       ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7'))
   ]))
   
   story.append(info_table)
   story.append(PageBreak())
   
   # 學習統計分析
   story.append(Paragraph('Learning Statistics Analysis', heading_style))
   story.append(Spacer(1, 20))
   
   if study_sessions:
       # 統計數據
       total_minutes = sum(s.duration_minutes for s in study_sessions)
       total_hours = total_minutes / 60
       
       attention_sessions = [s for s in study_sessions if s.avg_attention]
       if attention_sessions:
           avg_attention = sum(s.avg_attention for s in attention_sessions) / len(attention_sessions)
           avg_attention_percent = round(avg_attention * 100 / 3)
       else:
           avg_attention_percent = 0
       
       stats_data = [
           ['Total Study Time', f'{total_hours:.1f} hours ({total_minutes} minutes)'],
           ['Average Attention Level', f'{avg_attention_percent}%'],
           ['Study Frequency', f'{len(study_sessions)} sessions'],
           ['Average Session Duration', f'{total_minutes/len(study_sessions):.1f} minutes']
       ]
       
       stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
       stats_table.setStyle(TableStyle([
           ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F4F8')),
           ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
           ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
           ('FONTSIZE', (0, 0), (-1, -1), 11),
           ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
           ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#3498DB'))
       ]))
       
       story.append(stats_table)
       story.append(Spacer(1, 30))
       
       # 科目表現分析
       story.append(Paragraph('Subject Performance Analysis', heading_style))
       story.append(Spacer(1, 20))
       
       subject_stats = {}
       for session in study_sessions:
           if session.subject not in subject_stats:
               subject_stats[session.subject] = {
                   'count': 0,
                   'total_time': 0,
                   'attention_sum': 0,
                   'attention_count': 0
               }
           subject_stats[session.subject]['count'] += 1
           subject_stats[session.subject]['total_time'] += session.duration_minutes
           if session.avg_attention:
               subject_stats[session.subject]['attention_sum'] += session.avg_attention
               subject_stats[session.subject]['attention_count'] += 1
       
       subject_data = [['Subject', 'Sessions', 'Total Time', 'Avg Attention']]
       for subject, stats in subject_stats.items():
           subject_name = SUBJECTS.get(subject, subject)
           avg_att = 0
           if stats['attention_count'] > 0:
               avg_att = round(stats['attention_sum'] / stats['attention_count'] * 100 / 3)
           subject_data.append([
               subject_name,
               str(stats['count']),
               f"{stats['total_time']} min",
               f"{avg_att}%"
           ])
       
       subject_table = Table(subject_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
       subject_table.setStyle(TableStyle([
           ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
           ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
           ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
           ('FONTSIZE', (0, 0), (-1, -1), 11),
           ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
           ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
           ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#95A5A6'))
       ]))
       
       story.append(subject_table)
       story.append(PageBreak())
   
   # 個人化建議
   story.append(Paragraph('Personalized Learning Recommendations', heading_style))
   story.append(Spacer(1, 20))
   
   suggestions = generate_comprehensive_suggestions(child, study_sessions)
   
   # 建議分類顯示
   for category, items in suggestions.items():
       if items:
           category_names = {
               'learning_style': 'Learning Style Suggestions',
               'schedule': 'Schedule Optimization',
               'subject_specific': 'Subject-Specific Advice',
               'attention_improvement': 'Attention Improvement Tips',
               'age_appropriate': 'Age-Appropriate Recommendations'
           }
           
           story.append(Paragraph(category_names.get(category, category), heading_style))
           story.append(Spacer(1, 10))
           
           for item in items:
               story.append(Paragraph(f"• {item}", normal_style))
               story.append(Spacer(1, 8))
           
           story.append(Spacer(1, 20))
   
   # 生成報告
   doc.build(story)
   return filepath

def create_attention_chart(emotion_data, session_id):
   """建立專注度趨勢圖"""
   if not CHARTS_AVAILABLE:
       return None
       
   try:
       times = [(data.timestamp - emotion_data[0].timestamp).total_seconds() / 60 for data in emotion_data]
       attention_levels = [data.attention_level for data in emotion_data]
       
       plt.figure(figsize=(10, 6))
       plt.plot(times, attention_levels, 'b-', linewidth=2, markersize=4, marker='o')
       plt.title('Attention Level Trend', fontsize=16, fontweight='bold')
       plt.xlabel('Time (minutes)', fontsize=12)
       plt.ylabel('Attention Level', fontsize=12)
       plt.ylim(0, 4)
       plt.grid(True, alpha=0.3)
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
   if not CHARTS_AVAILABLE:
       return None
       
   try:
       emotions = [data.emotion for data in emotion_data if data.emotion]
       emotion_counts = {}
       
       for emotion in emotions:
           emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
       
       if not emotion_counts:
           return None
       
       plt.figure(figsize=(10, 6))
       bars = plt.bar(emotion_counts.keys(), emotion_counts.values(), 
                      color=['#3498DB', '#2ECC71', '#E74C3C', '#F39C12', '#9B59B6', '#1ABC9C'])
       plt.title('Emotion Distribution', fontsize=16, fontweight='bold')
       plt.xlabel('Emotion Type', fontsize=12)
       plt.ylabel('Frequency', fontsize=12)
       plt.xticks(rotation=45)
       
       # 添加數值標籤
       for bar in bars:
           height = bar.get_height()
           plt.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom')
       
       plt.tight_layout()
       
       chart_path = f'reports/emotion_chart_{session_id}.png'
       plt.savefig(chart_path, dpi=300, bbox_inches='tight')
       plt.close()
       
       return chart_path
   except Exception as e:
       print(f"建立情緒分布圖表時發生錯誤: {e}")
       return None

@app.route('/update_profile', methods=['POST'])
def update_profile():
   """更新個人資料"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   data = request.get_json()
   user_id = session['user_id']
   
   user = User.query.get(user_id)
   if user:
       # 更新使用者資料
       if data.get('email'):
           # 檢查郵件是否已被使用
           existing_user = User.query.filter_by(email=data['email']).first()
           if existing_user and existing_user.id != user_id:
               return jsonify({'success': False, 'message': '此電子郵件已被使用'})
           user.email = data['email']
       
       if data.get('password'):
           user.password_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
       
       db.session.commit()
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到使用者'})

@app.route('/update_child/<int:child_id>', methods=['POST'])
def update_child(child_id):
   """更新小孩資料"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   data = request.get_json()
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   
   if child:
       child.nickname = data.get('nickname', child.nickname)
       child.age = int(data.get('age', child.age))
       child.gender = data.get('gender', child.gender)
       child.education_stage = data.get('education_stage', child.education_stage)
       
       db.session.commit()
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到該小孩檔案'})

@app.route('/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
   """刪除單次學習記錄"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   # 驗證此學習記錄屬於當前使用者的小孩
   study_session = StudySession.query.join(Child).filter(
       StudySession.id == session_id,
       Child.user_id == session['user_id']
   ).first()
   
   if study_session:
       db.session.delete(study_session)
       db.session.commit()
       return jsonify({'success': True})
   
   return jsonify({'success': False, 'message': '找不到該學習記錄'})

@app.route('/get_calendar_data')
def get_calendar_data():
   """獲取日曆數據"""
   if 'user_id' not in session or 'child_id' not in session:
       return jsonify({'success': False})
   
   child_id = session['child_id']
   study_sessions = StudySession.query.filter_by(child_id=child_id).all()
   
   calendar_data = []
   for session in study_sessions:
       calendar_data.append({
           'date': session.start_time.strftime('%Y-%m-%d'),
           'subject': SUBJECTS.get(session.subject, session.subject),
           'duration': session.duration_minutes,
           'attention': round(session.avg_attention * 100 / 3) if session.avg_attention else 0
       })
   
   return jsonify({'success': True, 'data': calendar_data})

@app.route('/logout')
def logout():
   """登出功能"""
   session.clear()
   return redirect(url_for('index'))

if __name__ == '__main__':
   with app.app_context():
       db.create_all()
   app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))