# Chat Resume 🤖📝

AI-powered resume parsing and editing platform with real-time preview and intelligent content analysis.

## ✨ Features

- 🤖 **AI-Powered Resume Parsing** - Uses DEEPSEEK API for intelligent text extraction and structuring
- 📝 **Real-time Editing** - Live preview as you edit your resume content
- 🎯 **Smart Project Recognition** - Accurately identifies and extracts project experiences
- 📊 **Quality Scoring** - AI-driven resume quality assessment and suggestions
- 💼 **Professional Templates** - Multiple resume formats and export options
- 🔧 **Robust Error Handling** - Dynamic timeout configuration and retry mechanisms
- 📱 **Responsive Design** - Works seamlessly on desktop, tablet, and mobile

## 🏗️ Architecture

### Frontend
- **Next.js 14** - React framework with App Router
- **React 18** - Modern React with hooks and suspense
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Framer Motion** - Smooth animations

### Backend
- **FastAPI** - High-performance Python web framework
- **SQLAlchemy** - Database ORM with relationship mapping
- **PostgreSQL** - Robust relational database
- **Redis** - Caching and session management
- **Alembic** - Database migration management

### AI Integration
- **DEEPSEEK API** - Advanced language model for text processing
- **Dynamic Timeout** - Adaptive processing time based on content complexity
- **Retry Mechanisms** - Robust error handling for API calls

### File Processing
- **PDF Support** - Extract text from PDF resumes using pdfplumber
- **DOCX Support** - Microsoft Word document processing
- **TXT Support** - Plain text file handling
- **Multi-format Export** - Generate resumes in various formats

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL
- Redis

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/849261680/chat-resume.git
   cd chat-resume
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   
   # Copy environment file and configure
   cp .env.example .env
   # Edit .env with your database and API credentials
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   
   # Copy environment file and configure
   cp .env.example .env.local
   # Edit .env.local with your API endpoints
   ```

### Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql://username:password@localhost/chat_resume
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
```

**Frontend (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Running the Application

1. **Start Backend**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start Frontend**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## 📊 AI Resume Parser

### How It Works

1. **File Upload** - Supports PDF, DOCX, and TXT formats
2. **Text Extraction** - Intelligently extracts text while preserving structure
3. **AI Processing** - DEEPSEEK API analyzes and structures the content
4. **Quality Assessment** - Calculates completeness and accuracy scores
5. **Real-time Preview** - Instantly displays parsed results

### Dynamic Timeout System

The parser automatically adjusts processing time based on content complexity:
- **Short resumes** (<2000 chars): 60 seconds
- **Medium resumes** (2000-3000 chars): 75 seconds  
- **Long resumes** (>3000 chars): 90 seconds

### Supported Content Types

- ✅ Personal Information (name, contact, social links)
- ✅ Education Background (schools, degrees, dates)
- ✅ Work Experience (companies, positions, descriptions)
- ✅ Technical Skills (categorized by type)
- ✅ Projects (technologies, roles, achievements)
- ✅ Achievements and Certifications

## 🛠️ Development

### Project Structure

```
chat-resume/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Configuration
│   │   ├── models/         # Database models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components
│   │   └── lib/           # Utilities
│   └── package.json
└── README.md
```

### Database Migrations

```bash
cd backend
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🚀 Deployment

### Railway.app (Recommended)

1. **Connect GitHub Repository**
   - Link your repository to Railway
   - Set environment variables in Railway dashboard

2. **Backend Deployment**
   - Railway will automatically detect the Procfile
   - Set `RAILWAY_SERVICE_TYPE=backend`

3. **Frontend Deployment**
   - Deploy frontend separately or use Vercel
   - Update API URL in environment variables

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build
```

## 📈 Performance Features

- **Async Processing** - Non-blocking AI API calls
- **Connection Pooling** - Efficient database connections
- **Caching** - Redis-based session and data caching
- **Lazy Loading** - Progressive component loading
- **Error Boundaries** - Graceful error handling
- **Loading States** - User-friendly progress indicators

## 🔒 Security

- **JWT Authentication** - Secure token-based auth
- **Input Validation** - Comprehensive data sanitization
- **File Type Validation** - Restricted upload formats
- **Rate Limiting** - API abuse prevention
- **CORS Configuration** - Cross-origin security
- **Environment Isolation** - Separate configs per environment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **DEEPSEEK** - AI language model for intelligent text processing
- **FastAPI** - Modern Python web framework
- **Next.js** - React framework for production
- **Tailwind CSS** - Utility-first CSS framework

## 📞 Support

For questions and support:
- 📧 Email: support@chat-resume.com
- 🐛 Issues: [GitHub Issues](https://github.com/849261680/chat-resume/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/849261680/chat-resume/discussions)

---

**Built with ❤️ using AI-assisted development**