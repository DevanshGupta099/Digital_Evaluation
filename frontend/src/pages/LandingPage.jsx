import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo.jsx'

export default function LandingPage() {
  return (
    <div className="landing-page">
      {/* Header */}
      <header className="landing-header">
        <div className="brand">
          <Logo />
          DigitalEval
        </div>
        <nav>
          <Link to="/dashboard" className="nav-link">Login</Link>
          <Link to="/dashboard" className="button primary">Go to Dashboard</Link>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="hero-section split section-bg-dark">
        <div className="hero-text-block">
          <h1 className="hero-title">
            Intelligent Grading, <br/>
            <span className="highlight">Perfected by AI.</span>
          </h1>
          <p className="hero-subtitle">
            An end-to-end evaluation pipeline. Upload your question paper, answer key, and scanned handwritten student scripts. Our dual-LLM infrastructure handles handwriting OCR, semantic evaluation, and visual annotation in seconds.
          </p>
          <div className="hero-actions-inline">
            <Link to="/dashboard/new" className="button primary large">Start New Evaluation</Link>
            <Link to="/dashboard" className="button secondary large">View Queue</Link>
          </div>
        </div>
        
        {/* CSS Mockup - Hero Graphic */}
        <div className="hero-image-block">
          <div className="css-mockup floating-mockup">
            <div className="mockup-header">
              <span className="mockup-dot red"></span>
              <span className="mockup-dot yellow"></span>
              <span className="mockup-dot green"></span>
            </div>
            <div className="mockup-body">
              <div className="mockup-line title"></div>
              <div className="mockup-line"></div>
              <div className="mockup-line short"></div>
              <div className="mockup-grade-badge">
                A+ <span>(100%)</span>
              </div>
              <div className="mockup-check">✓ Fully Verified</div>
            </div>
          </div>
        </div>
      </section>

      {/* Trusted By Section */}
      <section className="trusted-by section-bg-glass">
        <p>TRUSTED BY EDUCATORS WORLDWIDE</p>
        <div className="trusted-logos">
          <span>Stanford</span>
          <span>MIT</span>
          <span>Oxford</span>
          <span>Harvard</span>
          <span>Cambridge</span>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works section-bg-slate">
        <h2>The Complete Lifecycle Explained</h2>
        <p className="section-description">A transparent, four-step pipeline transforming raw handwriting into verifiable grades.</p>
        <div className="steps-container">
          <div className="step-card">
            <div className="step-number">01</div>
            <h3>1. Rubric Generation</h3>
            <p>Upload your Question Paper and Answer Key. Our AI analyzes the syllabus structure and auto-generates a structured grading rubric with precise point allocations.</p>
          </div>
          <div className="step-card">
            <div className="step-number">02</div>
            <h3>2. Handwriting OCR & Segmentation</h3>
            <p>Upload a raw PDF of a student's handwritten answer script. Using advanced vision models, the system accurately transcribes the cursive and segments the answers by question.</p>
          </div>
          <div className="step-card">
            <div className="step-number">03</div>
            <h3>3. Dual-Model Evaluation</h3>
            <p>Each answer is independently graded by two state-of-the-art LLMs (Gemini & Groq). The models debate the conceptual correctness to prevent bias, awarding partial marks intelligently.</p>
          </div>
          <div className="step-card">
            <div className="step-number">04</div>
            <h3>4. Human-in-the-Loop Audit</h3>
            <p>You have the final say. Access an interactive dashboard to review line-by-line annotations, resolve LLM disagreements, and instantly override any AI decision.</p>
          </div>
        </div>
      </section>

      {/* Deep-Dive Feature Showcase */}
      <section className="feature-showcase section-bg-dark">
        <div className="feature-split">
          
          {/* CSS Mockup - Dashboard Overview */}
          <div className="feature-img-container">
            <div className="css-mockup dashboard-mockup">
              <div className="mockup-sidebar">
                <div className="sidebar-line"></div>
                <div className="sidebar-line active"></div>
                <div className="sidebar-line"></div>
              </div>
              <div className="mockup-main">
                <div className="mockup-stat-grid">
                  <div className="mockup-stat"></div>
                  <div className="mockup-stat"></div>
                  <div className="mockup-stat"></div>
                </div>
                <div className="mockup-table">
                  <div className="table-row head"></div>
                  <div className="table-row"></div>
                  <div className="table-row"></div>
                  <div className="table-row"></div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="feature-text">
            <h2>Actionable Analytics & Verifiable Annotations</h2>
            <p>
              DigitalEval doesn't just output a number. It outputs a complete audit trail ensuring every mark is justified.
            </p>
            <ul className="feature-list">
              <li><strong>Line-by-line references</strong> proving exactly where the student earned their marks.</li>
              <li><strong>Interactive Review Dashboard</strong> letting you override any AI decision with a single click.</li>
              <li><strong>Flagged discrepancies</strong> automatically routing edge-cases to human evaluators.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Privacy & Security */}
      <section className="privacy-section section-bg-glass">
        <h2>Enterprise-Grade Security</h2>
        <p>Your student data is sacred. We enforce strict privacy controls so you can evaluate with peace of mind.</p>
        <div className="privacy-grid">
          <div className="privacy-card">
            <h4>No AI Training</h4>
            <p>Your question papers, answer keys, and student scripts are strictly sandboxed and never used to train public LLM models.</p>
          </div>
          <div className="privacy-card">
            <h4>Encrypted Data</h4>
            <p>All data is encrypted in transit and at rest using industry-standard AES-256 protocols.</p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="faq-section section-bg-slate">
        <h2>Frequently Asked Questions</h2>
        <div className="faq-grid">
          <div className="faq-item">
            <h4>Can it read terrible handwriting?</h4>
            <p>Yes. Our OCR engine leverages state-of-the-art vision models to decipher cursive, scribbles, and poor scans with remarkable accuracy.</p>
          </div>
          <div className="faq-item">
            <h4>What if the AI makes a mistake?</h4>
            <p>You always have the final say. Our dashboard flags low-confidence grades and allows you to override the AI's marks instantly.</p>
          </div>
          <div className="faq-item">
            <h4>Does it work with diagrams?</h4>
            <p>Currently, the AI evaluates text-based answers. Diagrams and charts are extracted and highlighted for manual human review.</p>
          </div>
          <div className="faq-item">
            <h4>Can it grade conceptual answers?</h4>
            <p>Absolutely. It doesn't rely on keyword matching. It understands synonyms, phrasing variations, and awards partial credit intelligently based on your rubric.</p>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="cta-section section-bg-dark">
        <h2>Ready to transform your evaluation process?</h2>
        <p>Start your first AI-assisted evaluation today. No credit card required.</p>
        <Link to="/dashboard/new" className="button primary large" style={{marginTop: '24px'}}>Get Started for Free</Link>
      </section>
      
      <footer className="landing-footer section-bg-dark">
        <p>&copy; 2026 DigitalEval Inc. All Rights Reserved.</p>
      </footer>
    </div>
  )
}
