import { useEffect, useRef, useState } from 'react';
import {
  downloadAgent3ReportExcel,
  getAgent2Domains,
  getAgent3Report,
  runAgent2Chat,
  scoreAgent3Domain,
  uploadComplianceReport,
} from './api';

function App() {
  const apiKey = 'demo-key-123';
  const authEmailValue = 'user@gmail.com';
  const authPasswordValue = '123456';

  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authError, setAuthError] = useState('');

  const [selectedFile, setSelectedFile] = useState(null);
  const [agent1Loading, setAgent1Loading] = useState(false);
  const [agent1Error, setAgent1Error] = useState('');
  const [agent1Result, setAgent1Result] = useState(null);

  const [domains, setDomains] = useState([]);
  const [selectedDomain, setSelectedDomain] = useState('');
  const [agent2Loading, setAgent2Loading] = useState(false);
  const [agent2Error, setAgent2Error] = useState('');
  const [agent2Result, setAgent2Result] = useState(null);
  const [requestedDomain, setRequestedDomain] = useState('');
  const agent2RunRef = useRef(0);

  const [agent3ScoreLoading, setAgent3ScoreLoading] = useState(false);
  const [agent3ScoreError, setAgent3ScoreError] = useState('');
  const [agent3ScoreResult, setAgent3ScoreResult] = useState(null);
  const [agent3ReportLoading, setAgent3ReportLoading] = useState(false);
  const [agent3ReportError, setAgent3ReportError] = useState('');
  const [agent3Report, setAgent3Report] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined;
    }

    let cancelled = false;

    const loadDomains = async () => {
      try {
        const data = await getAgent2Domains(apiKey);
        if (cancelled) {
          return;
        }

        const loadedDomains = data.domains || [];
        setDomains(loadedDomains);
        setSelectedDomain((prev) => {
          if (prev && loadedDomains.some((item) => item.key === prev)) {
            return prev;
          }
          return loadedDomains[0]?.key || '';
        });
      } catch (err) {
        if (!cancelled) {
          setAgent2Error(err.message);
        }
      }
    };

    loadDomains();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, apiKey]);

  const handleLoginSubmit = (event) => {
    event.preventDefault();
    setAuthError('');

    const isValidEmail = loginEmail.trim().toLowerCase() === authEmailValue;
    const isValidPassword = loginPassword === authPasswordValue;

    if (!isValidEmail || !isValidPassword) {
      setAuthError('Invalid email or password.');
      return;
    }

    setIsAuthenticated(true);
    setLoginPassword('');
    setShowPassword(false);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setLoginEmail('');
    setLoginPassword('');
    setShowPassword(false);
    setAuthError('');
  };

  const handleAgent1Submit = async (event) => {
    event.preventDefault();
    setAgent1Error('');
    setAgent1Result(null);

    if (!selectedFile) {
      setAgent1Error('Please select a PDF file.');
      return;
    }

    setAgent1Loading(true);
    try {
      const data = await uploadComplianceReport(selectedFile, apiKey);
      setAgent1Result(data);
    } catch (err) {
      setAgent1Error(err.message);
    } finally {
      setAgent1Loading(false);
    }
  };

  const effectiveReportName = agent1Result?.report_name || '';

  const handleAgent3ScoreDomain = async () => {
    setAgent3ScoreError('');
    setAgent3ScoreResult(null);

    if (!agent2Result) {
      setAgent3ScoreError('Run Agent 2 first to score the current domain.');
      return;
    }

    if (!effectiveReportName) {
      setAgent3ScoreError('Report name is required. Upload a report first with Agent 1.');
      return;
    }

    setAgent3ScoreLoading(true);
    try {
      const data = await scoreAgent3Domain(
        {
          report_name: effectiveReportName,
          agent2_result: agent2Result,
        },
        apiKey
      );
      setAgent3ScoreResult(data);
    } catch (err) {
      setAgent3ScoreError(err.message);
    } finally {
      setAgent3ScoreLoading(false);
    }
  };

  const handleAgent3GenerateReport = async () => {
    setAgent3ReportError('');
    setAgent3Report(null);

    if (!effectiveReportName) {
      setAgent3ReportError('Report name is required to build final report.');
      return;
    }

    setAgent3ReportLoading(true);
    try {
      const data = await getAgent3Report(effectiveReportName, apiKey);
      setAgent3Report(data);
    } catch (err) {
      setAgent3ReportError(err.message);
    } finally {
      setAgent3ReportLoading(false);
    }
  };

  const handleAgent3DownloadExcel = async () => {
    setAgent3ReportError('');

    if (!effectiveReportName) {
      setAgent3ReportError('Report name is required to download Excel.');
      return;
    }

    try {
      const blob = await downloadAgent3ReportExcel(effectiveReportName, apiKey);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${effectiveReportName}_agent3_risk_report.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setAgent3ReportError(err.message);
    }
  };

  const handleAgent2Run = async () => {
    setAgent2Error('');
    setAgent2Result(null);

    if (!selectedDomain) {
      setAgent2Error('Please select a domain.');
      return;
    }

    setAgent2Loading(true);
    setRequestedDomain(selectedDomain);
    const runId = agent2RunRef.current + 1;
    agent2RunRef.current = runId;

    try {
      const data = await runAgent2Chat(
        {
          domain: selectedDomain,
          top_k: 5,
          report_name: effectiveReportName || null,
          max_loops: 5,
        },
        apiKey
      );
      if (runId === agent2RunRef.current) {
        setAgent2Result(data);
      }
    } catch (err) {
      if (runId === agent2RunRef.current) {
        setAgent2Error(err.message);
      }
    } finally {
      if (runId === agent2RunRef.current) {
        setAgent2Loading(false);
      }
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-top">
          <h1>CypherAi: An AI-Driven CyberSecurity and Compliance Automation Bot</h1>
          {isAuthenticated ? (
            <button type="button" className="secondary-btn logout-btn" onClick={handleLogout}>
              Logout
            </button>
          ) : null}
        </div>
        <p>Secure document intelligence, reasoning workflows, and deterministic risk reporting.</p>
      </header>

      {!isAuthenticated ? (
        <section className="card auth-card">
          <h2>Login</h2>
          <form className="auth-form" onSubmit={handleLoginSubmit}>
            <label>
              Email
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="user@gmail.com"
              />
            </label>

            <label>
              Password
              <div className="password-input-wrap">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="123456"
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7Zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Z" />
                    <circle cx="12" cy="12" r="2.5" />
                  </svg>
                </button>
              </div>
            </label>

            <button type="submit">Login</button>
          </form>
          {authError ? <p className="error">{authError}</p> : null}
        </section>
      ) : (
        <>
          <section className="card">
            <h2>Document Processing Using SecureBert</h2>
            <form onSubmit={handleAgent1Submit}>
              <label>
                Compliance Report (PDF)
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                />
              </label>

              <button type="submit" disabled={agent1Loading}>
                {agent1Loading ? 'Processing...' : 'Upload and Process'}
              </button>
            </form>

            {agent1Error ? <p className="error">{agent1Error}</p> : null}

            {agent1Result ? (
              <div className="result-block">
                <p><strong>Report:</strong> {agent1Result.report_name}</p>
                <p><strong>Total Pages:</strong> {agent1Result.total_pages}</p>
                <p><strong>Pages with Extracted Text:</strong> {agent1Result.pages_with_text}</p>
                <p><strong>Total Chunks:</strong> {agent1Result.total_chunks}</p>
                <p><strong>Embedding Dimension:</strong> {agent1Result.embedding_dimension}</p>
                <p><strong>Total Vectors in FAISS:</strong> {agent1Result.stored_vector_count}</p>
              </div>
            ) : null}
          </section>

          <section className="card">
            <h2>RAG+LLM Reasoning+Chain Of Thoughts</h2>

            <div className="controls-grid single-control">
              <label>
                Domain
                <select
                  value={selectedDomain}
                  disabled={agent2Loading}
                  onChange={(e) => setSelectedDomain(e.target.value)}
                >
                  {domains.map((domain) => (
                    <option key={domain.key} value={domain.key}>
                      {domain.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <button onClick={handleAgent2Run} disabled={agent2Loading}>
              {agent2Loading ? 'Running Agent 2...' : 'Run Agent 2'}
            </button>

            {agent2Error ? <p className="error">{agent2Error}</p> : null}

            {agent2Result ? (
              <div className="chat-wrap">
                <div className="chat-summary">
                  <p><strong>Requested Domain:</strong> {requestedDomain || '-'}</p>
                  <p><strong>Domain:</strong> {agent2Result.domain}</p>
                  <p><strong>Loops Run:</strong> {agent2Result.loops_run}</p>
                  <p><strong>Coverage Complete:</strong> {String(agent2Result.coverage_complete)}</p>
                  <p>
                    <strong>Coverage Score:</strong> {agent2Result.final_coverage_score} (threshold: {agent2Result.threshold})
                  </p>
                </div>

                {agent2Result.conversation.map((item) => (
                  <div key={item.loop_number} className="loop-block">
                    <div className="chat-row left">
                      <div className="chat-bubble query">
                        <p className="meta">Control Query - Loop {item.loop_number}</p>
                        <p>{item.control_query}</p>
                      </div>
                    </div>

                    <div className="chat-row right">
                      <div className="chat-bubble answer">
                        <p className="meta">LLM Answer - Loop {item.loop_number}</p>
                        <p><strong>Summary:</strong> {item.llm_answer.summary || 'No summary returned.'}</p>
                        <p><strong>Best Practices Found:</strong> {item.llm_answer.best_practices_found.join(', ') || 'None'}</p>
                        <p><strong>Risk Indicators Found:</strong> {item.llm_answer.risk_indicators_found.join(', ') || 'None'}</p>
                        <p><strong>Missing Areas:</strong> {item.llm_answer.missing_areas.join(', ') || 'None'}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="card">
            <h2>Risk Scoring &amp; Report Generation</h2>
            <p>
              <strong>Report Name:</strong> {effectiveReportName || 'Not set'}
            </p>

            <div className="agent3-actions">
              <button onClick={handleAgent3ScoreDomain} disabled={agent3ScoreLoading}>
                {agent3ScoreLoading ? 'Scoring Domain...' : 'Score Current Domain'}
              </button>
              <button onClick={handleAgent3GenerateReport} disabled={agent3ReportLoading}>
                {agent3ReportLoading ? 'Generating Report...' : 'Generate Final Report'}
              </button>
              <button onClick={handleAgent3DownloadExcel} className="secondary-btn">
                Download Excel Report
              </button>
            </div>

            {agent3ScoreError ? <p className="error">{agent3ScoreError}</p> : null}
            {agent3ReportError ? <p className="error">{agent3ReportError}</p> : null}

            {agent3ScoreResult ? (
              <div className="result-block">
                <p><strong>Domain:</strong> {agent3ScoreResult.domain}</p>
                <p><strong>Domain Score:</strong> {agent3ScoreResult.domain_score}</p>
                <p><strong>Threshold:</strong> {agent3ScoreResult.threshold}</p>
                <p><strong>Passes Threshold:</strong> {String(agent3ScoreResult.passes_threshold)}</p>
                <p><strong>Risk Level:</strong> {agent3ScoreResult.risk_level}</p>
              </div>
            ) : null}

            {agent3Report ? (
              <div className="result-block">
                <p><strong>Overall Status:</strong> {agent3Report.overall_status}</p>
                <p><strong>Aggregate Score:</strong> {agent3Report.aggregate_score}</p>
                <p><strong>Average Threshold:</strong> {agent3Report.average_threshold}</p>
                <p>
                  <strong>Domains:</strong> {agent3Report.total_domains_scored} (
                  {agent3Report.domains_meeting_threshold} pass / {agent3Report.domains_below_threshold} below)
                </p>

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Domain</th>
                        <th>Score</th>
                        <th>Threshold</th>
                        <th>Status</th>
                        <th>Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agent3Report.domain_results.map((item) => (
                        <tr key={item.domain}>
                          <td>{item.domain}</td>
                          <td>{item.domain_score}</td>
                          <td>{item.threshold}</td>
                          <td>{item.passes_threshold ? 'Pass' : 'Fail'}</td>
                          <td>{item.risk_level}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}

export default App;
