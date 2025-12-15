"use client";

import { useState } from "react";
import MarkdownTable from "./MarkdownTable";

interface ExpandableTableProps {
  title: string;
  content: string;
  defaultOpen?: boolean;
}

export default function ExpandableTable({ title, content, defaultOpen = false }: ExpandableTableProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div style={{
      margin: '1rem 0',
      border: '1px solid #333',
      borderRadius: '8px',
      overflow: 'hidden'
    }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '12px 16px',
          backgroundColor: '#2a2a2a',
          color: '#e5e5e5',
          border: 'none',
          textAlign: 'left',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.95rem',
          fontWeight: 600,
          transition: 'background-color 0.2s'
        }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#333'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#2a2a2a'}
      >
        <span>{title}</span>
        <span style={{
          fontSize: '1.2rem',
          transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s'
        }}>
          ▶
        </span>
      </button>
      
      {isOpen && (
        <div style={{
          padding: '0',
          backgroundColor: '#1a1a1a'
        }}>
          <MarkdownTable content={content} />
        </div>
      )}
    </div>
  );
}




