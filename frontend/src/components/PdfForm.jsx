import React, { useState } from 'react';
import { Upload, Send } from 'lucide-react';
import './PsfForm.css';

export default function PsfForm() {
  const [document, setDocument] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [question, setQuestion] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);

  const handleUpload = async (file) => {
    try {
      setIsUploading(true);
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');

      const doc = await response.json();
      setDocument(doc);
      setQuestions([]);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload PDF. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!document || !question.trim() || isAsking) return;

    try {
      setIsAsking(true);
      const response = await fetch('http://localhost:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: document.id,
          question: question.trim(),
        }),
      });

      if (!response.ok) throw new Error('Failed to get answer');

      const answer = await response.json();
      setQuestions(prev => [...prev, answer]);
      setQuestion('');
    } catch (error) {
      console.error('Question failed:', error);
      alert('Failed to get answer. Please try again.');
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <div className="logo">
          <img src="/planet-logo.png" alt="Planet Logo" />
        </div>
        {!document && (
          <button className="upload-btn">
            <Upload size={16} />
            Upload PDF
          </button>
        )}
      </header>

      <main className="chat-main">
        {!document ? (
          <div 
            className="upload-area"
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file?.type === 'application/pdf') handleUpload(file);
            }}
            onDragOver={(e) => e.preventDefault()}
          >
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="upload-label">
              {isUploading ? 'Uploading...' : 'Drop your PDF here'}
            </label>
          </div>
        ) : (
          <div className="chat-messages">
            {questions.map((q) => (
              <div key={q.id} className="message">
                <p className="question">{q.question}</p>
                <p className="answer">{q.answer}</p>
              </div>
            ))}
          </div>
        )}
      </main>

      {document && (
        <footer className="chat-footer">
          <form onSubmit={handleAsk} className="message-form">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Send a message..."
              disabled={isAsking}
            />
            <button type="submit" disabled={isAsking || !question.trim()}>
              <Send size={16} />
            </button>
          </form>
        </footer>
      )}
    </div>
  );
}