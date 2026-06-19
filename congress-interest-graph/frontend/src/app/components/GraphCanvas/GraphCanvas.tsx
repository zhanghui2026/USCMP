import { useEffect, useRef } from 'react';
import { Graph } from '@antv/g6';
import type { GraphResponse, GraphNode, GraphEdge } from '../../api/types';

interface Props {
  graph: GraphResponse;
  onDoubleClickNode: (nodeId: string) => void;
  onEdgeClick: (claimId: string) => void;
  height?: string | number;
  personImages?: Record<string, string>;
}

const EDGE_COLORS: Record<string, string> = {
  SERVES_IN: '#1890ff',
  REPRESENTS_STATE: '#52c41a',
  MEMBER_OF_PARTY: '#722ed1',
  ASSIGNED_TO: '#fa8c16',
  EDUCATED_AT: '#13c2c2',
  HELD_POSITION: '#faad14',
  EMPLOYED_BY: '#ff7a45',
  HAS_PROFILE_SOURCE: '#b37feb',
  BACKGROUND_RELATION: '#d9d9d9',
};

const NODE_COLORS: Record<string, string> = {
  Person: '#1890ff',
  BackgroundPerson: '#bfbfbf',
  Party: '#722ed1',
  State: '#52c41a',
  Chamber: '#fa8c16',
  Committee: '#eb2f96',
  PoliticalEntity: '#eb2f96',
  EducationInstitution: '#13c2c2',
  Position: '#faad14',
  Employer: '#ff7a45',
  ProfileSource: '#b37feb',
};

const NODE_SHAPES: Record<string, string> = {
  Person: 'circle',
  BackgroundPerson: 'circle',
  Party: 'diamond',
  State: 'rect',
  Chamber: 'hexagon',
  Committee: 'rect',
  PoliticalEntity: 'diamond',
  EducationInstitution: 'rect',
  Position: 'diamond',
  Employer: 'rect',
  ProfileSource: 'hexagon',
};

export default function GraphCanvas({ graph, onDoubleClickNode, onEdgeClick, height = 600, personImages = {} }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const g6Ref = useRef<Graph | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;

    if (graph.nodes.length > 500) {
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const g6Data: any = {
      nodes: graph.nodes.map((n) => {
        const imgUrl = n.label === 'Person' ? (personImages[n.id] || null) : null;
        return {
          id: n.id,
          data: {
            label: sanitizeGraphLabel(getNodeLabelRaw(n)),
            nodeType: n.label,
            color: NODE_COLORS[n.label] || '#8c8c8c',
            size: getNodeSize(n),
            imgUrl,
          },
          style: {
            fill: imgUrl ? '#0a0e17' : (NODE_COLORS[n.label] || '#8c8c8c'),
            size: getNodeSize(n),
            ...(imgUrl ? {
              icon: {
                type: 'image',
                src: imgUrl,
                width: getNodeSize(n) - 4,
                height: getNodeSize(n) - 4,
              },
            } : {}),
          },
        };
      }),
      edges: graph.edges.map((e) => {
        const isLowConfidence = e.confidence_score !== undefined && e.confidence_score < 0.5;
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          data: e,
          style: {
            stroke: EDGE_COLORS[e.type] || '#6b7280',
            lineWidth: isLowConfidence ? 1 : 2,
            lineDash: isLowConfidence ? [4, 4] : undefined,
            opacity: isLowConfidence ? 0.4 : 0.8,
          },
        };
      }),
    };

    const g6 = new Graph({
      container,
      width,
      height: typeof height === 'number' ? height : 600,
      autoFit: 'view',
      layout: {
        type: 'radial' as const,
        unitRadius: 100,
        preventOverlap: true,
        linkDistance: 120,
      },
      node: {
        style: {
          labelText: (d: Record<string, unknown>) => {
            const data = (d.data || d) as Record<string, unknown>;
            const raw = data.label ?? d.id;
            return sanitizeGraphLabel(raw) as string;
          },
          labelFontSize: 10,
          labelFill: '#e5e7eb',
          labelPlacement: 'bottom',
          labelWordWrap: true,
          labelMaxWidth: 120,
        },
      },
      edge: {
        style: {
          endArrow: true,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });

    g6.setData(g6Data);
    g6.render();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    g6.on('node:click', (evt: any) => {
      const nodeId = evt?.target?.id as string;
      if (nodeId) onDoubleClickNode(nodeId);
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    g6.on('edge:click', (evt: any) => {
      const edgeData = evt?.target?.data;
      const claimId = edgeData?.claim_id as string;
      if (claimId) onEdgeClick(claimId);
    });

    g6Ref.current = g6;

    return () => {
      g6.destroy();
      g6Ref.current = null;
    };
  }, [graph]);

  if (graph.nodes.length > 500) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#faad14', fontSize: 16, flexDirection: 'column', gap: 8,
      }}>
        <div>图谱节点过多 ({graph.nodes.length} &gt; 500)</div>
        <div style={{ fontSize: 13, color: '#6b7280' }}>请缩小查询范围后重试</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ height, width: '100%', background: '#0a0e17', overflow: 'hidden' }}
    />
  );
}

function getNodeLabelRaw(node: GraphNode): string {
  const props = node.properties;
  return (props.display_name || props.canonical_name || props.name || props.title || node.id) as string;
}

const MAX_LABEL_LENGTH = 30;

export function sanitizeGraphLabel(raw: unknown): string {
  if (raw === null || raw === undefined) return "Unknown";
  if (typeof raw === "object") {
    if (Array.isArray(raw)) return "(list)";
    return "(data)";
  }
  let text = String(raw).replace(/\n/g, " ").replace(/\s+/g, " ").trim();
  if (text.length === 0) return "Unknown";
  if (text.length > MAX_LABEL_LENGTH) {
    text = text.slice(0, MAX_LABEL_LENGTH) + "...";
  }
  return text;
}

function getNodeSize(node: GraphNode): number {
  const sizes: Record<string, number> = {
    Person: 40, Party: 28, State: 24, Chamber: 32, Committee: 20,
    PoliticalEntity: 32,
    EducationInstitution: 24, Position: 22, Employer: 24, ProfileSource: 20,
  };
  return sizes[node.label] || 24;
}
