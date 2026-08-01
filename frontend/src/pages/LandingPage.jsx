import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo.jsx'
import { motion } from 'framer-motion'
import { useEffect } from 'react'
import Lenis from '@studio-freight/lenis'

export default function LandingPage() {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      direction: 'vertical',
      gestureDirection: 'vertical',
      smooth: true,
      mouseMultiplier: 1,
      smoothTouch: false,
      touchMultiplier: 2,
      infinite: false,
    })
    function raf(time) {
      lenis.raf(time)
      requestAnimationFrame(raf)
    }
    requestAnimationFrame(raf)
    return () => {
      lenis.destroy()
    }
  }, [])
  return (
    <div className="lp-container">
      {/* Navigation */}
      <nav className="lp-nav">
        <div className="lp-nav-content">
          <div className="lp-brand">
            <Logo />
            <span>DigitalEval</span>
          </div>
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#security">Security</a>
            <a href="#faq">FAQ</a>
            <Link to="/dashboard" className="lp-login-btn">Login</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="lp-hero">
        <div className="lp-hero-bg">
          <div className="lp-glow lp-glow-1"></div>
          <div className="lp-glow lp-glow-2"></div>
          <div className="lp-grid-pattern"></div>
        </div>
        
        <div className="lp-hero-content">
          <motion.div 
            className="lp-pill"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="lp-pill-badge">New</span> 
            <span>Powered by Dual-Model AI Architecture</span>
          </motion.div>
          
          <motion.h1 
            className="lp-h1"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            Evaluation, <br />
            <span className="lp-text-gradient">redefined.</span>
          </motion.h1>
          
          <motion.p 
            className="lp-hero-subtitle"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            DigitalEval transforms raw handwritten scripts into verifiable, pixel-perfect grades. Upload your paper, sit back, and let our infrastructure handle the rest.
          </motion.p>
          
          <motion.div 
            className="lp-hero-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <Link to="/dashboard/new" className="lp-btn lp-btn-primary">
              Start Evaluating 
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
            </Link>
            <Link to="/dashboard" className="lp-btn lp-btn-secondary">View Dashboard</Link>
          </motion.div>
        </div>
      </section>

      {/* Logos Section */}
      <section className="lp-logos">
        <p>TRUSTED BY WORLD-CLASS UNIVERSITIES</p>
        <div className="lp-logos-row">
          <span>Stanford</span>
          <span>MIT</span>
          <span>Oxford</span>
          <span>Harvard</span>
          <span>Cambridge</span>
        </div>
      </section>

      {/* Deep Dive Features */}
      <section id="features" className="lp-features">
        <div className="lp-section-header">
          <h2 className="lp-h2">The Pipeline</h2>
          <p className="lp-subtitle">A transparent, deterministic four-step flow.</p>
        </div>

        <div className="lp-pipeline-container">
          <motion.div className="lp-pipeline-line" initial={{ height: 0 }} whileInView={{ height: "100%" }} viewport={{ once: true }} transition={{ duration: 1.5, ease: "easeInOut" }}></motion.div>
          
          <motion.div className="lp-pipeline-step" initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.8, type: "spring" }}>
            <div className="lp-pipeline-dot"></div>
            <div className="lp-pipeline-content">
              <div className="lp-pipeline-text">
                <div className="lp-step-num">STEP 01</div>
                <h3>Automated Rubric Parsing</h3>
                <p>Upload your Question Paper and Answer Key in PDF format. We intelligently parse the syllabus structure into a strict grading rubric.</p>
              </div>
              <div className="lp-pipeline-visual">
                <img src="/feature_rubric.png" alt="Automated Rubric Parsing" className="lp-feature-img" style={{width: '100%', maxWidth: 'none'}} />
              </div>
            </div>
          </motion.div>

          <motion.div className="lp-pipeline-step" initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.8, type: "spring" }}>
            <div className="lp-pipeline-dot" style={{borderColor: '#ec4899', boxShadow: '0 0 20px rgba(236, 72, 153, 0.8)'}}></div>
            <div className="lp-pipeline-content">
              <div className="lp-pipeline-text">
                <div className="lp-step-num" style={{background: 'rgba(236, 72, 153, 0.2)', color: '#f472b6'}}>STEP 02</div>
                <h3>State-of-the-Art OCR</h3>
                <p>Handwriting isn't a problem. Our vision models transcribe cursive, scribbles, and faded ink with near-perfect accuracy.</p>
              </div>
              <div className="lp-pipeline-visual">
                <img src="/feature_ocr.png" alt="OCR Scanning" className="lp-feature-img" style={{width: '100%', maxWidth: 'none'}} />
              </div>
            </div>
          </motion.div>

          <motion.div className="lp-pipeline-step" initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} transition={{ duration: 0.8, type: "spring" }}>
            <div className="lp-pipeline-dot" style={{borderColor: '#3b82f6', boxShadow: '0 0 20px rgba(59, 130, 246, 0.8)'}}></div>
            <div className="lp-pipeline-content">
              <div className="lp-pipeline-text">
                <div className="lp-step-num" style={{background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa'}}>STEP 03</div>
                <h3>Dual-Model Auditing</h3>
                <p>Every answer is graded by two independent LLMs. If they disagree, the discrepancy is immediately flagged for human review.</p>
              </div>
              <div className="lp-pipeline-visual">
                <img src="/feature_ai.png" alt="Dual-Model AI" className="lp-feature-img" style={{width: '100%', maxWidth: 'none'}} />
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Security Section */}
      <section id="security" className="lp-security">
        <div className="lp-section-header">
          <h2 className="lp-h2">Enterprise-Grade Security</h2>
          <p className="lp-subtitle">We protect your student data like our own.</p>
        </div>
        
        <div className="lp-cards-grid">
          <div className="lp-card">
            <div className="lp-icon">🛡️</div>
            <h4>No AI Training</h4>
            <p>Your data is sandboxed. It is never used to train public LLM models.</p>
          </div>
          <div className="lp-card">
            <div className="lp-icon">🔒</div>
            <h4>End-to-End Encryption</h4>
            <p>AES-256 encryption at rest and TLS 1.3 in transit.</p>
          </div>
          <div className="lp-card">
            <div className="lp-icon">⚙️</div>
            <h4>Private VPC Deployment</h4>
            <p>Deploy directly inside your university's private cloud network.</p>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="lp-faq">
        <div className="lp-section-header">
          <h2 className="lp-h2">Frequently Asked Questions</h2>
        </div>
        
        <div className="lp-faq-grid">
          <div className="lp-faq-item">
            <h4>Can it read terrible handwriting?</h4>
            <p>Yes. Our OCR engine leverages state-of-the-art vision models to decipher cursive, scribbles, and poor scans with remarkable accuracy.</p>
          </div>
          <div className="lp-faq-item">
            <h4>What if the AI makes a mistake?</h4>
            <p>You always have the final say. Our dashboard flags low-confidence grades and allows you to override the AI's marks instantly.</p>
          </div>
          <div className="lp-faq-item">
            <h4>Does it work with diagrams?</h4>
            <p>Currently, the AI evaluates text-based answers. Diagrams and charts are extracted and highlighted for manual human review.</p>
          </div>
          <div className="lp-faq-item">
            <h4>Can it grade conceptual answers?</h4>
            <p>Absolutely. It doesn't rely on keyword matching. It understands synonyms, phrasing variations, and awards partial credit intelligently based on your rubric.</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="lp-cta">
        <div className="lp-social-proof">
          <div className="lp-avatars">
            <div className="lp-avatar" style={{background: '#3b82f6'}}></div>
            <div className="lp-avatar" style={{background: '#8b5cf6'}}></div>
            <div className="lp-avatar" style={{background: '#ec4899'}}></div>
            <div className="lp-avatar" style={{background: '#10b981'}}></div>
          </div>
          <span>Join 5,000+ top educators worldwide</span>
        </div>
        
        <h2 className="lp-h2">Ready to evolve?</h2>
        <p className="lp-subtitle">Deploy your first AI evaluation pipeline in seconds. No credit card required.</p>
        
        <div className="lp-cta-buttons">
          <Link to="/dashboard/new" className="lp-btn lp-btn-primary cta">Get Started</Link>
          <a href="#" className="lp-btn lp-btn-outline">View Documentation</a>
        </div>
      </section>

      {/* Footer */}
      <footer className="lp-footer">
        <div className="lp-footer-content">
          <div className="lp-footer-brand">
            <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
              <Logo /> <span style={{fontSize: '1.4rem', fontWeight: 800}}>DigitalEval</span>
            </div>
            <p style={{marginTop: '8px', maxWidth: '300px', lineHeight: '1.6'}}>
              The standard in AI assessment. We are building the future of automated, deterministic grading for educational institutions worldwide.
            </p>
          </div>
          <div className="lp-footer-links">
            <div className="lp-footer-col">
              <strong>Product</strong>
              <a href="#">Features</a>
              <a href="#">Security</a>
              <a href="#">Pricing</a>
              <a href="#">Changelog</a>
            </div>
            <div className="lp-footer-col">
              <strong>Company</strong>
              <a href="#">About Us</a>
              <a href="#">Blog</a>
              <a href="#">Careers</a>
              <a href="#">Contact</a>
            </div>
            <div className="lp-footer-col">
              <strong>Legal</strong>
              <a href="#">Privacy Policy</a>
              <a href="#">Terms of Service</a>
              <a href="#">Cookie Policy</a>
            </div>
          </div>
        </div>
        <div className="lp-footer-bottom">
          <div className="lp-footer-bottom-content">
            <span>&copy; 2026 DigitalEval Inc. All rights reserved.</span>
            <div className="lp-footer-social">
              <a href="#">Twitter</a>
              <a href="#">GitHub</a>
              <a href="#">LinkedIn</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
