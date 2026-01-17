"use client";

import React from "react";

type FactsCardTopMove = {
  move?: string;
  eval_cp?: number;
};

type FactsCardProps = {
  title?: string;
  eval_cp?: number;
  recommended_move?: string;
  recommended_reason?: string;
  top_moves?: FactsCardTopMove[];
  source?: string;
};

export default function FactsCard(props: FactsCardProps) {
  const evalText = typeof props.eval_cp === "number" ? `${props.eval_cp}cp` : "—";
  const top = Array.isArray(props.top_moves) ? props.top_moves.slice(0, 5) : [];

  if (
    props.eval_cp === undefined &&
    !props.recommended_move &&
    (!props.top_moves || props.top_moves.length === 0)
  ) {
    return null;
  }

  return (
    <div className="facts-card">
      <div className="facts-card-header">
        <div className="facts-card-title">{props.title || "Facts"}</div>
        <div className="facts-card-eval">Eval: {evalText}</div>
      </div>

      {props.recommended_move && (
        <div className="facts-card-row">
          <div className="facts-card-label">Candidate</div>
          <div className="facts-card-value">
            <strong>{props.recommended_move}</strong>
            {props.recommended_reason ? (
              <span className="facts-card-muted"> ({props.recommended_reason})</span>
            ) : null}
          </div>
        </div>
      )}

      {top.length > 0 && (
        <div className="facts-card-row">
          <div className="facts-card-label">Top</div>
          <div className="facts-card-value">
            {top.map((m, idx) => (
              <span key={`${m.move || "?"}-${idx}`} className="facts-card-chip">
                {m.move || "?"}
                {typeof m.eval_cp === "number" ? <span className="facts-card-muted"> {m.eval_cp}cp</span> : null}
              </span>
            ))}
          </div>
        </div>
      )}

      {props.source && (
        <div className="facts-card-footer">
          <span className="facts-card-muted">source: {props.source}</span>
        </div>
      )}
    </div>
  );
}





