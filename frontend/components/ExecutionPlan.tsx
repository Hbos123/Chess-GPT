"use client";

import React, { useState } from 'react';

interface ExecutionStep {
  step_number: number;
  action_type: string;
  parameters: Record<string, any>;
  purpose: string;
  tool_to_call: string | null;
  expected_output: string;
  status: "pending" | "in_progress" | "completed" | "failed";
}

interface ExecutionPlanProps {
  plan_id: string;
  steps: ExecutionStep[];
  total_steps: number;
  onStepClick?: (step: ExecutionStep) => void;
  isComplete?: boolean;
  thinkingTimeSeconds?: number;
}

export default function ExecutionPlan({ 
  plan_id, 
  steps, 
  total_steps,
  onStepClick,
  isComplete = false,
  thinkingTimeSeconds
}: ExecutionPlanProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [isCollapsed, setIsCollapsed] = useState(isComplete); // Auto-collapse when complete
  
  const toggleStep = (stepNumber: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepNumber)) {
      newExpanded.delete(stepNumber);
    } else {
      newExpanded.add(stepNumber);
    }
    setExpandedSteps(newExpanded);
  };
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return "✓";
      case "in_progress":
        return "⟳";
      case "failed":
        return "✗";
      default:
        return " ";
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "rgba(76, 175, 80, 0.8)";
      case "in_progress":
        return "rgba(33, 150, 243, 0.8)";
      case "failed":
        return "rgba(244, 67, 54, 0.8)";
      default:
        return "rgba(255, 255, 255, 0.3)";
    }
  };
  
  const completedCount = steps.filter(s => s.status === "completed").length;
  const progressPercentage = total_steps > 0 ? (completedCount / total_steps) * 100 : 0;
  const allCompleted = completedCount === total_steps;
  
  return (
    <div className="execution-plan">
      <div className="execution-plan-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <button 
            className="execution-plan-toggle"
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'rgba(255, 255, 255, 0.7)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '0 4px'
            }}
          >
            {isCollapsed ? '▶' : '▼'}
          </button>
          <h3>
            {isComplete && thinkingTimeSeconds 
              ? `Thought for ${thinkingTimeSeconds}s` 
              : 'Execution Plan'}
          </h3>
        </div>
        {!isCollapsed && (
          <div className="execution-plan-progress">
            <span>{completedCount}/{total_steps} steps</span>
            <div className="execution-plan-progress-bar">
              <div 
                className="execution-plan-progress-fill"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        )}
      </div>
      
      {!isCollapsed && (
        <div className="execution-plan-steps">
        {steps.map((step) => {
          const isExpanded = expandedSteps.has(step.step_number);
          const statusColor = getStatusColor(step.status);
          
          return (
            <div 
              key={step.step_number}
              className={`execution-plan-step execution-plan-step-${step.status}`}
              onClick={() => onStepClick ? onStepClick(step) : toggleStep(step.step_number)}
            >
              <div className="execution-plan-step-header">
                <span 
                  className="execution-plan-step-checkbox"
                  style={{ color: statusColor }}
                >
                  [{getStatusIcon(step.status)}]
                </span>
                <span className="execution-plan-step-number">
                  Step {step.step_number}:
                </span>
                <span className="execution-plan-step-purpose">
                  {step.purpose}
                </span>
                <span className="execution-plan-step-action">
                  {step.action_type}
                </span>
              </div>
              
              {isExpanded && (
                <div className="execution-plan-step-details">
                  <div className="execution-plan-step-detail">
                    <strong>Action:</strong> {step.action_type}
                  </div>
                  {step.tool_to_call && (
                    <div className="execution-plan-step-detail">
                      <strong>Tool:</strong> {step.tool_to_call}
                    </div>
                  )}
                  {step.expected_output && (
                    <div className="execution-plan-step-detail">
                      <strong>Expected:</strong> {step.expected_output}
                    </div>
                  )}
                  {Object.keys(step.parameters).length > 0 && (
                    <div className="execution-plan-step-detail">
                      <strong>Parameters:</strong>
                      <pre>{JSON.stringify(step.parameters, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      )}
      
      <style jsx>{`
        .execution-plan {
          background: rgba(30, 30, 30, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 12px;
          margin: 8px 0;
          font-size: 13px;
        }
        
        .execution-plan-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .execution-plan-header h3 {
          margin: 0;
          font-size: 14px;
          color: rgba(255, 255, 255, 0.9);
        }
        
        .execution-plan-progress {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .execution-plan-progress span {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.6);
          min-width: 50px;
        }
        
        .execution-plan-progress-bar {
          width: 100px;
          height: 4px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 2px;
          overflow: hidden;
        }
        
        .execution-plan-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, rgba(76, 175, 80, 0.6), rgba(76, 175, 80, 0.9));
          transition: width 0.3s ease-out;
        }
        
        .execution-plan-steps {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        
        .execution-plan-step {
          padding: 8px;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.15s ease;
          border-left: 3px solid transparent;
        }
        
        .execution-plan-step:hover {
          background: rgba(255, 255, 255, 0.05);
        }
        
        .execution-plan-step-pending {
          border-left-color: rgba(255, 255, 255, 0.3);
        }
        
        .execution-plan-step-in_progress {
          border-left-color: rgba(33, 150, 243, 0.8);
          background: rgba(33, 150, 243, 0.05);
        }
        
        .execution-plan-step-completed {
          border-left-color: rgba(76, 175, 80, 0.8);
          background: rgba(76, 175, 80, 0.05);
        }
        
        .execution-plan-step-failed {
          border-left-color: rgba(244, 67, 54, 0.8);
          background: rgba(244, 67, 54, 0.05);
        }
        
        .execution-plan-step-header {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        
        .execution-plan-step-checkbox {
          font-family: monospace;
          font-size: 12px;
          min-width: 20px;
        }
        
        .execution-plan-step-number {
          color: rgba(255, 255, 255, 0.7);
          font-weight: 500;
        }
        
        .execution-plan-step-purpose {
          color: rgba(255, 255, 255, 0.9);
          flex: 1;
        }
        
        .execution-plan-step-action {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.5);
          background: rgba(255, 255, 255, 0.1);
          padding: 2px 6px;
          border-radius: 3px;
        }
        
        .execution-plan-step-details {
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          font-size: 12px;
        }
        
        .execution-plan-step-detail {
          margin: 4px 0;
          color: rgba(255, 255, 255, 0.7);
        }
        
        .execution-plan-step-detail strong {
          color: rgba(255, 255, 255, 0.9);
          margin-right: 6px;
        }
        
        .execution-plan-step-detail pre {
          margin: 4px 0 0 16px;
          padding: 4px 8px;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 3px;
          font-size: 11px;
          overflow-x: auto;
        }
      `}</style>
    </div>
  );
}

