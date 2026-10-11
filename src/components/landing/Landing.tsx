import { useState } from 'react';
import { ArrowRight, BriefcaseBusiness, FolderKanban, House, LayoutGrid, LockKeyhole, Menu, Search, Sparkles, X } from 'lucide-react';
import { EmployeeLogin } from './EmployeeLogin';
import './landing.css';

interface LandingProps {
  configured: boolean;
  pendingGoal: string;
  onGoalChange: (value: string) => void;
}

const quickGoals = [
  { label: 'Prepare for a client meeting', prompt: 'Prepare for my next client meeting with Acme Corp.' },
  { label: 'Investigate product usage', prompt: 'Investigate why Acme Corp product usage has dropped.' },
  { label: 'Review project delivery', prompt: 'Review projects that are falling behind schedule.' },
  { label: 'Organize upcoming work', prompt: 'Show my priorities and upcoming work.' },
];

const navItems = [
  { label: 'Home', icon: House },
  { label: 'Workspace', icon: LayoutGrid },
  { label: 'Projects', icon: FolderKanban },
  { label: 'AI Assistant', icon: Sparkles },
  { label: 'Resources', icon: BriefcaseBusiness },
];

export function Landing({ configured, pendingGoal, onGoalChange }: LandingProps) {
  const [loginOpen, setLoginOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const openLogin = () => {
    setMobileMenuOpen(false);
    setLoginOpen(true);
  };

  function prepareGoal(event: React.FormEvent) {
    event.preventDefault();
    openLogin();
  }

  return <div className="kairos-landing">
    <div className="landing-surface">
      <header className="landing-header">
        <a className="landing-brand" href="#home" aria-label="KAIROS home">
          <span className="landing-logo" aria-hidden="true"><span className="landing-gate"/></span>
          <span className="landing-brand-names"><strong>カイロス</strong><small>KAIROS</small></span>
        </a>
        <nav className="landing-desktop-nav" aria-label="Main navigation">
          {navItems.map((item, i) => <button key={item.label} type="button" className={i === 0 ? 'landing-nav-item current' : 'landing-nav-item'} onClick={i === 0 ? () => window.scrollTo({ top: 0, behavior: 'smooth' }) : openLogin}>
            <item.icon size={17} strokeWidth={1.9}/>{item.label}
          </button>)}
        </nav>
        <div className="landing-header-actions">
          <button type="button" className="landing-search" aria-label="Access KAIROS search after signing in" onClick={openLogin}><Search size={18}/></button>
          <button type="button" className="landing-signin-link" onClick={openLogin}><LockKeyhole size={16}/> Employee sign in <ArrowRight size={15}/></button>
          <button type="button" className="landing-mobile-menu-btn" onClick={() => setMobileMenuOpen(v => !v)} aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'} aria-expanded={mobileMenuOpen}>{mobileMenuOpen ? <X size={21}/> : <Menu size={21}/>}</button>
        </div>
      </header>
      {mobileMenuOpen && <nav className="landing-mobile-menu" aria-label="Mobile navigation">{navItems.map((item,i)=><button key={item.label} onClick={i===0?()=>{setMobileMenuOpen(false);window.scrollTo({top:0,behavior:'smooth'})}:openLogin}><item.icon size={18}/>{item.label}</button>)}<button onClick={openLogin}><LockKeyhole size={18}/>Employee sign in</button></nav>}

      <main id="home">
        <section className="landing-hero" aria-labelledby="landing-heading">
          <div className="landing-hero-wash" aria-hidden="true"/>
          <div className="landing-art" aria-hidden="true"><img src="/images/kairos-japan-hero.webp" alt=""/></div>
          <div className="landing-petal petal-a" aria-hidden="true"/>
          <div className="landing-petal petal-b" aria-hidden="true"/>
          <div className="landing-petal petal-c" aria-hidden="true"/>
          <div className="landing-petal petal-d" aria-hidden="true"/>
          <div className="landing-petal petal-e" aria-hidden="true"/>
          <div className="landing-petal petal-f" aria-hidden="true"/>
          <div className="landing-hero-content">
            <p className="landing-kicker">INTELLIGENT WORKSPACE FOR SORYU SYSTEMS</p>
            <div className="landing-product-title" lang="ja">カイロス<span className="landing-flower" aria-hidden="true">✿</span></div>
            <h1 id="landing-heading">From intent to impact,<br/>at the right moment.</h1>
            <p className="landing-description">KAIROS understands your goals and assembles the right information, tools and actions into one adaptive workspace.</p>
            <form className="landing-intent" onSubmit={prepareGoal}>
              <Sparkles size={20} aria-hidden="true"/>
              <label className="landing-sr-only" htmlFor="landing-goal">What would you like to accomplish?</label>
              <input id="landing-goal" value={pendingGoal} onChange={event=>onGoalChange(event.target.value)} placeholder="Tell KAIROS what you want to do..." maxLength={500}/>
              <button type="submit" aria-label="Continue to employee sign in"><ArrowRight size={20}/></button>
            </form>
            <div className="landing-prompt-chips" aria-label="Suggested goals">
              {quickGoals.map(item => <button type="button" key={item.label} onClick={()=>{onGoalChange(item.prompt);openLogin();}}>{item.label}</button>)}
            </div>
          </div>
          <div className="landing-bottom-note"><span className="landing-note-line"/>DESIGNED AROUND YOU, NOT THE OTHER WAY AROUND</div>
        </section>
        <section className="landing-value-section" aria-label="What KAIROS helps you do">
          <div className="landing-value-intro"><span>THE KAIROS APPROACH</span><h2>A workspace shaped<br/>around your next move.</h2></div>
          <div className="landing-value-grid">
            <article><span className="landing-value-icon"><Sparkles size={23}/></span><h3>Understand your intent</h3><p>Describe the outcome you need, not the menus you have to open.</p></article>
            <article><span className="landing-value-icon"><LayoutGrid size={23}/></span><h3>Adapt the interface</h3><p>Surface useful data and real tools in a task-specific workspace.</p></article>
            <article><span className="landing-value-icon"><LockKeyhole size={23}/></span><h3>Work with confidence</h3><p>Keep your work within SORYU SYSTEMS' secure employee environment.</p></article>
          </div>
        </section>
      </main>
      <footer className="landing-footer"><span>KAIROS <span lang="ja">カイロス</span></span><span>Intelligence for SORYU SYSTEMS</span><button type="button" onClick={openLogin}>Employee access <ArrowRight size={14}/></button></footer>
    </div>
    {loginOpen && <EmployeeLogin configured={configured} onClose={() => setLoginOpen(false)}/>}
  </div>;
}
