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
   # 移除 best_subject_of_day 欄位，改用動態計算
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

def upgrade_database():
    """升級資料庫結構"""
    try:
        # 檢查是否需要升級
        with app.app_context():
            # 嘗試查詢現有表結構
            result = db.engine.execute("PRAGMA table_info(study_session)")
            columns = [row[1] for row in result]
            
            # 如果沒有 best_subject_of_day 欄位，則不需要做任何事情
            # 因為我們已經從模型中移除了這個欄位
            print("資料庫結構檢查完成")
            
    except Exception as e:
        print(f"資料庫升級過程中發生錯誤: {e}")

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
   
   # 驗證年齡範圍
   try:
       age = int(age)
       if age < 6 or age > 18:
           return jsonify({'success': False, 'message': '年齡必須在6-18歲之間'})
   except (ValueError, TypeError):
       return jsonify({'success': False, 'message': '請輸入有效的年齡'})
   
   # 檢查是否已達到4個小孩的限制
   existing_children = Child.query.filter_by(user_id=session['user_id']).count()
   if existing_children >= 4:
       return jsonify({'success': False, 'message': '最多只能創建4個小孩檔案'})
   
   # 創建新的小孩檔案
   child = Child(
       user_id=session['user_id'],
       nickname=nickname,
       gender=gender,
       age=age,
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
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   
   if not child:
       return redirect(url_for('child_selection'))
   
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
   
   child = Child.query.filter_by(id=session['child_id'], user_id=session['user_id']).first()
   
   if not child:
       return redirect(url_for('child_selection'))
   
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
   session['session_start_time'] = datetime.utcnow().isoformat()
   
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
       
       # 計算實際學習時間（分鐘整數）
       if 'session_start_time' in session:
           start_time = datetime.fromisoformat(session['session_start_time'])
           actual_duration = (datetime.utcnow() - start_time).total_seconds() / 60
           current_study_session.duration_minutes = int(actual_duration)
       
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
       session.pop('session_start_time', None)
       
       return jsonify({'success': True, 'session_id': session_id})
   
   return jsonify({'success': False, 'message': '找不到學習階段'})

def get_best_subject_for_date(child_id, date):
   """獲取指定日期的最佳科目"""
   # 獲取該日期的所有學習記錄
   sessions = StudySession.query.filter(
       StudySession.child_id == child_id,
       db.func.date(StudySession.start_time) == date,
       StudySession.avg_attention.isnot(None)
   ).all()
   
   if not sessions:
       return None
   
   # 找出專注度最高的科目
   best_session = max(sessions, key=lambda x: x.avg_attention)
   return best_session.subject

@app.route('/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
   """刪除單次學習記錄"""
   if 'user_id' not in session or 'child_id' not in session:
       return jsonify({'success': False, 'message': '請先登入並選擇小孩'})
   
   # 確保這個學習記錄屬於當前用戶的小孩
   study_session = StudySession.query.filter_by(
       id=session_id, 
       child_id=session['child_id']
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
       return jsonify({'success': False, 'message': '請先登入並選擇小孩'})
   
   year = request.args.get('year', datetime.now().year, type=int)
   month = request.args.get('month', datetime.now().month, type=int)
   
   # 獲取指定月份的學習記錄
   start_date = datetime(year, month, 1)
   if month == 12:
       end_date = datetime(year + 1, 1, 1)
   else:
       end_date = datetime(year, month + 1, 1)
   
   sessions = StudySession.query.filter(
       StudySession.child_id == session['child_id'],
       StudySession.start_time >= start_date,
       StudySession.start_time < end_date
   ).all()
   
   # 按日期分組，找出每日最佳科目
   calendar_data = {}
   daily_subjects = {}
   
   for study_session in sessions:
       date_key = study_session.start_time.strftime('%Y-%m-%d')
       if date_key not in daily_subjects:
           daily_subjects[date_key] = []
       
       daily_subjects[date_key].append({
           'subject': study_session.subject,
           'attention': study_session.avg_attention or 0,
           'session_data': {
               'id': study_session.id,
               'subject': SUBJECTS.get(study_session.subject, study_session.subject),
               'duration_minutes': study_session.duration_minutes,
               'avg_attention': study_session.avg_attention,
               'start_time': study_session.start_time.strftime('%H:%M')
           }
       })
   
   # 為每天確定最佳科目和顏色
   for date_key, subjects in daily_subjects.items():
       if subjects:
           # 找出專注度最高的科目
           best_subject_data = max(subjects, key=lambda x: x['attention'])
           best_subject = best_subject_data['subject']
           
           # 根據科目分配顏色
           subject_colors = {
               'math': '#3498DB',      # 藍色
               'science': '#2ECC71',   # 綠色
               'language': '#E74C3C',  # 紅色
               'social': '#F39C12',    # 橙色
               'art': '#9B59B6',       # 紫色
               'cs': '#1ABC9C'         # 青色
           }
           
           calendar_data[date_key] = {
               'best_subject': best_subject,
               'color': subject_colors.get(best_subject, '#95A5A6'),
               'sessions': [s['session_data'] for s in subjects]
           }
   
   return jsonify({'success': True, 'data': calendar_data})

@app.route('/data_analysis')
def data_analysis():
   """數據分析頁面"""
   if 'user_id' not in session or 'child_id' not in session:
       return redirect(url_for('child_selection'))
   
   child = Child.query.filter_by(id=session['child_id'], user_id=session['user_id']).first()
   
   if not child:
       return redirect(url_for('child_selection'))
   
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
   
   child = Child.query.filter_by(id=session['child_id'], user_id=session['user_id']).first()
   
   if not child:
       return redirect(url_for('child_selection'))
   
   study_sessions = StudySession.query.filter_by(child_id=child.id).order_by(StudySession.start_time.asc()).all()
   
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

@app.route('/update_user_profile', methods=['POST'])
def update_user_profile():
   """更新使用者資料"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   data = request.get_json()
   user = User.query.get(session['user_id'])
   
   if user:
       new_username = data.get('username')
       new_email = data.get('email')
       new_password = data.get('password')
       
       # 檢查使用者名稱是否被其他人使用
       if new_username != user.username:
           existing_user = User.query.filter_by(username=new_username).first()
           if existing_user:
               return jsonify({'success': False, 'message': '使用者名稱已被使用'})
       
       # 檢查電子郵件是否被其他人使用
       if new_email != user.email:
           existing_email = User.query.filter_by(email=new_email).first()
           if existing_email:
               return jsonify({'success': False, 'message': '電子郵件已被使用'})
       
       # 更新資料
       user.username = new_username
       user.email = new_email
       
       if new_password:
           user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
       
       db.session.commit()
       session['username'] = new_username
       
       return jsonify({'success': True, 'message': '資料更新成功'})
   
   return jsonify({'success': False, 'message': '找不到使用者'})

@app.route('/update_child_profile', methods=['POST'])
def update_child_profile():
   """更新小孩資料"""
   if 'user_id' not in session:
       return jsonify({'success': False, 'message': '請先登入'})
   
   data = request.get_json()
   child_id = data.get('child_id')
   child = Child.query.filter_by(id=child_id, user_id=session['user_id']).first()
   
   if child:
       age = data.get('age')
       
       # 驗證年齡範圍
       try:
           age = int(age)
           if age < 6 or age > 18:
               return jsonify({'success': False, 'message': '年齡必須在6-18歲之間'})
       except (ValueError, TypeError):
           return jsonify({'success': False, 'message': '請輸入有效的年齡'})
       
       child.nickname = data.get('nickname')
       child.gender = data.get('gender')
       child.age = age
       child.education_stage = data.get('education_stage')
       
       db.session.commit()
       
       # 如果更新的是當前選中的小孩，更新session
       if session.get('child_id') == child_id:
           session['child_nickname'] = child.nickname
       
       return jsonify({'success': True, 'message': '小孩資料更新成功'})
   
   return jsonify({'success': False, 'message': '找不到小孩檔案'})

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
   
   # 基於年齡和教育階段的建議 - 統一推薦番茄鐘技巧
   suggestions['age_appropriate'].append("建議使用番茄鐘技巧：學習25分鐘，休息5分鐘，有助於維持專注力")
   
   if child.education_stage == 'elementary':
       if child.age <= 8:
           suggestions['age_appropriate'].append("年齡較小，建議搭配互動式學習活動和獎勵制度增加學習動機")
       else:
           suggestions['age_appropriate'].append("可以鼓勵自主選擇學習主題，提升學習興趣和責任感")
   elif child.education_stage == 'middle':
       suggestions['age_appropriate'].append("國中階段需要更多自主學習空間，建議設定明確的學習目標")
       suggestions['age_appropriate'].append("可以開始培養時間管理和學習計畫的能力")
   else:  # high school
       suggestions['age_appropriate'].append("高中生需要更強的自律性，建議制定長期學習計畫")
       suggestions['age_appropriate'].append("重視學習效率，可使用思維導圖、康乃爾筆記法等學習工具")
   
   # 基於性別的建議（避免刻板印象）
   if child.gender == 'female':
       suggestions['learning_style'].append("可以考慮與朋友一起學習，合作學習環境有助於學習效果")
   else:
       suggestions['learning_style'].append("可以設定挑戰性目標，競爭性學習環境較能激發學習動力")
   
   # 基於學習數據的時間規劃建議
   if study_sessions:
       # 專注度分析
       attention_sessions = [s for s in study_sessions if s.avg_attention]
       if attention_sessions:
           avg_attention = sum(s.avg_attention for s in attention_sessions) / len(attention_sessions)
           
           if avg_attention < 1.5:
               suggestions['attention_improvement'].append("專注度偏低，建議檢查學習環境是否有干擾因素")
               suggestions['attention_improvement'].append("可以嘗試使用白噪音或輕音樂幫助集中注意力")
               suggestions['schedule'].append("建議縮短每次學習時間至15-20分鐘，增加休息頻率")
           elif avg_attention < 2.5:
               suggestions['attention_improvement'].append("專注度中等，建議學習前做5分鐘的深呼吸或伸展運動")
               suggestions['schedule'].append("目前的25分鐘學習時段很適合，建議維持這個節奏")
           else:
               suggestions['attention_improvement'].append("專注度表現優秀！可以嘗試更有挑戰性的學習內容")
               suggestions['schedule'].append("可以考慮延長學習時段至30-35分鐘，但仍要保持適當休息")
       
       # 學習時間分析
       study_hours = {}
       for session in study_sessions:
           hour = session.start_time.hour
           if hour not in study_hours:
               study_hours[hour] = []
           if session.avg_attention:
               study_hours[hour].append(session.avg_attention)
       
       if study_hours:
           # 找出專注度最高的時段
           best_hour_data = max(study_hours.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0)
           best_hour = best_hour_data[0]
           
           if 6 <= best_hour < 9:
               suggestions['schedule'].append("您的孩子在早上(6-9點)專注度最高，建議安排重要科目在這個時段")
           elif 9 <= best_hour < 12:
               suggestions['schedule'].append("您的孩子在上午(9-12點)專注度最高，建議安排重要科目在這個時段")
           elif 14 <= best_hour < 17:
               suggestions['schedule'].append("您的孩子在下午(14-17點)專注度最高，建議安排重要科目在這個時段")
           elif 19 <= best_hour < 22:
               suggestions['schedule'].append("您的孩子在晚上(19-22點)專注度最高，建議安排重要科目在這個時段")
           
           # 根據年齡給予時間規劃建議
           if child.age <= 10:
               suggestions['schedule'].append("建議避免在晚上8點後進行需要高度專注的學習")
           elif child.age <= 15:
               suggestions['schedule'].append("可以在晚上9點前完成主要學習任務，之後進行輕鬆的複習")
           else:
               suggestions['schedule'].append("高中生可以適度延長晚間學習時間，但要確保充足睡眠")
       
       # 科目專屬建議
       subject_performance = {}
       for session in study_sessions:
           if session.avg_attention:
               if session.subject not in subject_performance:
                   subject_performance[session.subject] = []
               subject_performance[session.subject].append(session.avg_attention)
       
       for subject, performances in subject_performance.items():
           avg_perf = sum(performances) / len(performances)
           subject_name = SUBJECTS.get(subject, subject)
           
           if avg_perf < 2:
               if subject == 'math':
                   if child.education_stage == 'elementary':
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議使用數學遊戲和實物教具輔助學習")
                   else:
                       suggestions['subject_specific'].append(f"{subject_name}需要加強，建議多做基礎練習題，建立數學邏輯思維")
               elif subject == 'science':
                   suggestions['subject_specific'].append(f"{subject_name}需要加強，建議透過實驗和觀察增加學習興趣")
               else:
                   suggestions['subject_specific'].append(f"{subject_name}需要加強，建議增加練習時間並找出學習困難點")
           else:
               suggestions['subject_specific'].append(f"{subject_name}表現良好，可以嘗試更進階的內容或協助其他科目學習")
   
   return suggestions

def create_comprehensive_report(child, study_sessions):
   """創建包含數據分析和智慧建議的完整PDF報告"""
   filename = f'report_{child.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
   filepath = os.path.join('reports', filename)
   
   # 確保reports目錄存在
   os.makedirs('reports', exist_ok=True)
   
   doc = SimpleDocTemplate(filepath, pagesize=A4)
   story = []
   
   # 設定樣式
   styles = getSampleStyleSheet()
   
   # 自定義樣式
   title_style = ParagraphStyle(
       'CustomTitle',
       parent=styles['Title'],
       fontName='Helvetica-Bold',
       fontSize=24,
       textColor=colors.HexColor('#2C3E50'),
       alignment=TA_CENTER,
       spaceAfter=30
   )
   
   heading_style = ParagraphStyle(
       'CustomHeading',
       parent=styles['Heading1'],
       fontName='Helvetica-Bold',
       fontSize=16,
       textColor=colors.HexColor('#34495E'),
       spaceAfter=12
   )
   
   normal_style = ParagraphStyle(
       'CustomNormal',
       parent=styles['Normal'],
       fontName='Helvetica',
       fontSize=12,
       leading=18
   )
   
   # 標題頁
   story.append(Paragraph('Learning Assessment Report', title_style))
   story.append(Spacer(1, 30))
   
   # 基本資訊表格
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
   
   # 數據分析部分
   story.append(Paragraph('Data Analysis', heading_style))
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
   
   # 智慧建議部分
   story.append(Paragraph('Personalized Learning Recommendations', heading_style))
   story.append(Spacer(1, 20))
   
   suggestions = generate_comprehensive_suggestions(child, study_sessions)
   
   # 建議分類顯示
   category_names = {
       'age_appropriate': 'Age-Appropriate Recommendations',
       'learning_style': 'Learning Style Suggestions',
       'schedule': 'Schedule Optimization',
       'attention_improvement': 'Attention Improvement Tips',
       'subject_specific': 'Subject-Specific Advice'
   }
   
   for category, items in suggestions.items():
       if items:
           story.append(Paragraph(category_names.get(category, category), heading_style))
           story.append(Spacer(1, 10))
           
           for item in items:
               story.append(Paragraph(f"• {item}", normal_style))
               story.append(Spacer(1, 8))
           
           story.append(Spacer(1, 20))
   
   # 生成報告
   doc.build(story)
   return filepath

@app.route('/logout')
def logout():
   """登出功能"""
   session.clear()
   return redirect(url_for('index'))

if __name__ == '__main__':
   with app.app_context():
       db.create_all()
       # 執行資料庫升級檢查
       upgrade_database()
   app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))