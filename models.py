from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Request(db.Model):
    __tablename__ = 'requests'
    
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    req_date = db.Column(db.DateTime, default=datetime.now)
    temperature = db.Column(db.Float, nullable=False)
    max_tokens = db.Column(db.Integer, nullable=False)
    system_prompt = db.Column(db.Text)
    user_query = db.Column(db.Text, nullable=False)
    
    # Связь с ответами
    responses = db.relationship('Response', backref='request', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'request_id': self.request_id,
            'req_date': self.req_date.strftime('%Y-%m-%d %H:%M:%S'),
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'system_prompt': self.system_prompt,
            'user_query': self.user_query,
            'responses': [r.to_dict() for r in self.responses]
        }
    
    def get_formatted_date(self):
        """Форматированная дата для отображения в списке"""
        return self.req_date.strftime('%Y-%m-%d/%H:%M:%S')

class Response(db.Model):
    __tablename__ = 'responses'
    
    resp_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    req_id = db.Column(db.Integer, db.ForeignKey('requests.request_id'), nullable=False)
    agent_name = db.Column(db.String(100), nullable=False)
    resp_text = db.Column(db.Text)
    status = db.Column(db.String(20), default='success')  # 'success' или 'error'
    error_message = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'resp_id': self.resp_id,
            'agent_name': self.agent_name,
            'resp_text': self.resp_text,
            'status': self.status,
            'error_message': self.error_message
        }