// frontend/src/pages/SignalConfig.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

interface ProposedSignal {
  phrase: string;
  example_post: string;
  intent_strength: number;
}

type SignalStatus = "accepted" | "edited" | "rejected";

interface SignalSelection {
  proposed: ProposedSignal;
  status: SignalStatus;
  edited?: ProposedSignal;
}

type Step = 1 | 2 | 3 | 4 | 5;

const containerStyle: React.CSSProperties = {
  maxWidth: 720,
  margin: "0 auto",
  padding: "24px 16px",
};

const h1Style: React.CSSProperties = { fontSize: 24, marginBottom: 8, fontWeight: 600 };
const helpStyle: React.CSSProperties = { color: "#555", marginBottom: 16 };
const textareaStyle: React.CSSProperties = {
  width: "100%",
  minHeight: 128,
  padding: 12,
  border: "1px solid #ccc",
  borderRadius: 6,
  fontFamily: "inherit",
  fontSize: 14,
  boxSizing: "border-box",
};
const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: 12,
  border: "1px solid #ccc",
  borderRadius: 6,
  fontSize: 14,
  boxSizing: "border-box",
};
const primaryBtn: React.CSSProperties = {
  background: "#000",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "10px 16px",
  cursor: "pointer",
  fontSize: 14,
};
const secondaryBtn: React.CSSProperties = {
  background: "#fff",
  color: "#000",
  border: "1px solid #ccc",
  borderRadius: 6,
  padding: "10px 16px",
  cursor: "pointer",
  fontSize: 14,
};
const stepCounterStyle: React.CSSProperties = {
  fontSize: 13,
  color: "#888",
  marginBottom: 24,
};
const cardStyle: React.CSSProperties = {
  border: "1px solid #e2e2e2",
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};
const errorStyle: React.CSSProperties = { color: "#b00020", marginTop: 12 };

export function SignalConfig() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [whatYouSell, setWhatYouSell] = useState("");
  const [icp, setIcp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposalEventId, setProposalEventId] = useState<string | null>(null);
  const [selections, setSelections] = useState<SignalSelection[]>([]);
  // userAdded is wired for a future "Add custom signal" UI (Task 11+).
  // The v1 wizard only surfaces the LLM-proposed signals; leaving the setter
  // in place means the later UI can be added without refactoring state.
  const [userAdded] = useState<ProposedSignal[]>([]);

  const handlePropose = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post("/workspace/signals/propose", {
        what_you_sell: whatYouSell,
        icp: icp || null,
      });
      setProposalEventId(data.proposal_event_id);
      setSelections(
        data.signals.map((s: ProposedSignal) => ({
          proposed: s,
          status: "accepted" as const,
        })),
      );
      setStep(4);
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Failed to generate signals. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = (idx: number, status: SignalStatus) => {
    setSelections((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], status };
      return next;
    });
  };

  const updateEdit = (idx: number, field: keyof ProposedSignal, value: string | number) => {
    setSelections((prev) => {
      const next = [...prev];
      const current = next[idx].edited || { ...next[idx].proposed };
      next[idx] = {
        ...next[idx],
        status: "edited",
        edited: { ...current, [field]: value },
      };
      return next;
    });
  };

  const handleConfirm = async () => {
    if (!proposalEventId) return;
    setLoading(true);
    setError(null);
    const accepted: number[] = [];
    const edited: Array<{
      proposed_idx: number;
      final_phrase: string;
      final_example_post: string;
      final_intent_strength: number;
    }> = [];
    const rejected: number[] = [];
    selections.forEach((s, idx) => {
      if (s.status === "accepted") {
        accepted.push(idx);
      } else if (s.status === "edited" && s.edited) {
        edited.push({
          proposed_idx: idx,
          final_phrase: s.edited.phrase,
          final_example_post: s.edited.example_post,
          final_intent_strength: s.edited.intent_strength,
        });
      } else if (s.status === "rejected") {
        rejected.push(idx);
      }
    });
    try {
      await api.post("/workspace/signals/confirm", {
        proposal_event_id: proposalEventId,
        accepted,
        edited,
        rejected,
        user_added: userAdded,
      });
      navigate("/dashboard");
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Failed to save signals.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={containerStyle}>
      <div style={stepCounterStyle}>Step {step} of 5</div>

      {step === 1 && (
        <section>
          <h1 style={h1Style}>What do you sell?</h1>
          <p style={helpStyle}>
            In one or two sentences. Example: "Fractional CTO services for Series A-B SaaS
            startups with small engineering teams."
          </p>
          <textarea
            style={textareaStyle}
            value={whatYouSell}
            onChange={(e) => setWhatYouSell(e.target.value)}
          />
          <div style={{ marginTop: 16 }}>
            <button
              style={primaryBtn}
              disabled={whatYouSell.trim().length < 5}
              onClick={() => setStep(2)}
            >
              Next
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section>
          <h1 style={h1Style}>Who's your ICP? (optional)</h1>
          <p style={helpStyle}>
            Who are the people you sell to? Example: "CEOs and VPs Eng at 20-50 person
            startups."
          </p>
          <input
            style={inputStyle}
            value={icp}
            onChange={(e) => setIcp(e.target.value)}
          />
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <button style={secondaryBtn} onClick={() => setStep(1)}>
              Back
            </button>
            <button style={primaryBtn} onClick={() => setStep(3)}>
              Next
            </button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section>
          <h1 style={h1Style}>Generating signals...</h1>
          <p style={helpStyle}>This takes a few seconds.</p>
          {!loading && !proposalEventId && (
            <button style={primaryBtn} onClick={handlePropose}>
              Generate
            </button>
          )}
          {loading && <div>Thinking...</div>}
          {error && (
            <div style={errorStyle}>
              {error}{" "}
              <button
                onClick={handlePropose}
                style={{
                  background: "none",
                  border: "none",
                  textDecoration: "underline",
                  color: "#b00020",
                  cursor: "pointer",
                  padding: 0,
                  fontSize: "inherit",
                }}
              >
                Retry
              </button>
            </div>
          )}
        </section>
      )}

      {step === 4 && (
        <section>
          <h1 style={h1Style}>Review your signals</h1>
          <p style={helpStyle}>
            Accept, edit, or reject each one. Add your own if anything's missing.
          </p>
          {selections.map((sel, idx) => (
            <div key={idx} style={cardStyle}>
              <input
                style={{ ...inputStyle, fontWeight: 500 }}
                value={sel.edited?.phrase ?? sel.proposed.phrase}
                onChange={(e) => updateEdit(idx, "phrase", e.target.value)}
              />
              <div
                style={{
                  fontSize: 13,
                  color: "#666",
                  marginTop: 8,
                  fontStyle: "italic",
                }}
              >
                "{sel.proposed.example_post}"
              </div>
              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <button
                  onClick={() => updateStatus(idx, "accepted")}
                  style={{
                    ...secondaryBtn,
                    background: sel.status === "accepted" ? "#d4f7dc" : "#fff",
                  }}
                >
                  Accept
                </button>
                <button
                  onClick={() => updateStatus(idx, "rejected")}
                  style={{
                    ...secondaryBtn,
                    background: sel.status === "rejected" ? "#fad4d4" : "#fff",
                  }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <button style={secondaryBtn} onClick={() => setStep(3)}>
              Back
            </button>
            <button style={primaryBtn} onClick={() => setStep(5)}>
              Next
            </button>
          </div>
        </section>
      )}

      {step === 5 && (
        <section>
          <h1 style={h1Style}>Ready to save?</h1>
          <p style={helpStyle}>
            {selections.filter((s) => s.status !== "rejected").length + userAdded.length}{" "}
            signal(s) will be saved.
          </p>
          {error && <div style={errorStyle}>{error}</div>}
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <button style={secondaryBtn} onClick={() => setStep(4)}>
              Back
            </button>
            <button style={primaryBtn} disabled={loading} onClick={handleConfirm}>
              {loading ? "Saving..." : "Save and open dashboard"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

export default SignalConfig;
