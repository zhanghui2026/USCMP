import { useEffect, useRef, useState, useCallback } from 'react';
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
  ASSOCIATED_WITH_COMMITTEE: '#eb2f96',
  CONTRIBUTED_TO: '#ff4d4f',
  HAS_CONTRIBUTION_SOURCE: '#9254de',
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
  CampaignCommittee: '#eb2f96',
  Donor: '#ff4d4f',
  ContributionSource: '#9254de',
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
  CampaignCommittee: 'hexagon',
  Donor: 'diamond',
  ContributionSource: 'star',
};

function getNodeLabelRaw(node: GraphNode): string {
  const props = node.properties;
  return (props.display_name || props.canonical_name || props.name || props.title || node.id) as string;
}

const MAX_LABEL_LENGTH = 28;

export function sanitizeGraphLabel(raw: unknown): string {
  if (raw === null || raw === undefined) return 'Unknown';
  if (typeof raw === 'object') {
    if (Array.isArray(raw)) return '(list)';
    return '(data)';
  }
  let text = String(raw).replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
  if (text.length === 0) return 'Unknown';
  if (text.length > MAX_LABEL_LENGTH) {
    text = text.slice(0, MAX_LABEL_LENGTH) + '...';
  }
  return text;
}

function getNodeSize(node: GraphNode): number {
  const sizes: Record<string, number> = {
    Person: 44, Party: 32, State: 28, Chamber: 34, Committee: 24,
    PoliticalEntity: 34,
    EducationInstitution: 28, Position: 26, Employer: 28, ProfileSource: 24,
    CampaignCommittee: 30, Donor: 28, ContributionSource: 26,
  };
  return sizes[node.label] || 26;
}

export default function GraphCanvas({ graph, onDoubleClickNode, onEdgeClick, height = 600, personImages = {} }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const g6Ref = useRef<Graph | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });

  const updateSize = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setContainerSize({ width: Math.floor(rect.width), height: Math.floor(rect.height) });
    }
  }, []);

  useEffect(() => {
    updateSize();
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => updateSize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [updateSize]);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const { width, height: h } = containerSize;

    if (graph.nodes.length > 500) {
      return;
    }

    const g6Data: Record<string, unknown> = {
      nodes: graph.nodes.map((n) => {
        const imgUrl = n.label === 'Person' ? (personImages[n.id] || null) : null;
        const size = getNodeSize(n);
        return {
          id: n.id,
          data: {
            label: sanitizeGraphLabel(getNodeLabelRaw(n)),
            nodeType: n.label,
            color: NODE_COLORS[n.label] || '#8c8c8c',
            size,
            imgUrl,
          },
          style: {
            fill: imgUrl ? '#0a0e17' : (NODE_COLORS[n.label] || '#8c8c8c'),
            stroke: imgUrl ? NODE_COLORS[n.label] || '#8c8c8c' : undefined,
            lineWidth: imgUrl ? 2 : undefined,
            size,
            ...(imgUrl
              ? {
                  icon: {
                    type: 'image',
                    src: imgUrl,
                    width: size - 4,
                    height: size - 4,
                  },
                }
              : {}),
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
            lineWidth: isLowConfidence ? 1 : 2.5,
            lineDash: isLowConfidence ? [4, 4] : undefined,
            opacity: isLowConfidence ? 0.35 : 0.75,
            endArrow: {
              path: 'M 0,0 L 8,4 L 8,-4 Z',
              fill: EDGE_COLORS[e.type] || '#6b7280',
            },
          },
        };
      }),
    };

    const g6 = new Graph({
      container,
      width,
      height: h,
      autoFit: 'view',
      layout: {
        type: 'radial',
        unitRadius: 110,
        preventOverlap: true,
        linkDistance: 130,
        nodeSize: (d: Record<string, unknown>) => {
          const data = (d.data || d) as Record<string, unknown>;
          return (data.size as number) || 30;
        },
      },
      node: {
        style: {
          labelText: (d: Record<string, unknown>) => {
            const data = (d.data || d) as Record<string, unknown>;
            const raw = data.label ?? d.id;
            return sanitizeGraphLabel(raw);
          },
          labelFontSize: 8,
          labelFill: '#d1d5db',
          labelPlacement: 'bottom',
          labelWordWrap: true,
          labelMaxWidth: 100,
          labelBackground: true,
          labelBackgroundFill: '#111827',
          labelBackgroundOpacity: 0.85,
          labelBackgroundRadius: 3,
        },
      },
      edge: {
        style: {
          endArrow: true,
          labelText: (e: Record<string, unknown>) => {
            const d = e.data as Record<string, unknown>;
            const edgeType = d?.type as string;
            const labelMap: Record<string, string> = {
              SERVES_IN: '任职',
              REPRESENTS_STATE: '代表',
              MEMBER_OF_PARTY: '党派',
              ASSIGNED_TO: '委员会',
              EDUCATED_AT: '教育',
              HELD_POSITION: '职位',
              EMPLOYED_BY: '雇主',
              HAS_PROFILE_SOURCE: '来源',
              BACKGROUND_RELATION: '关联',
              ASSOCIATED_WITH_COMMITTEE: '竞选委员会',
              CONTRIBUTED_TO: '捐赠',
              HAS_CONTRIBUTION_SOURCE: '数据来源',
            };
            return labelMap[edgeType] || '';
          },
          labelFontSize: 7,
          labelFill: '#6b7280',
          labelBackground: true,
          labelBackgroundFill: '#0a0e17',
          labelBackgroundOpacity: 0.7,
          labelPadding: [1, 3],
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      animation: true,
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
  }, [graph, containerSize]);

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

  const hasFinanceNodes = graph.nodes.some(
    (n) => n.label === 'CampaignCommittee' || n.label === 'Donor' || n.label === 'ContributionSource'
  );

  return (
    <div style={{ position: 'relative', height, width: '100%' }}>
      <div
        ref={containerRef}
        style={{ height: '100%', width: '100%', background: '#0a0e17', overflow: 'hidden' }}
      />
      {hasFinanceNodes && (
        <div style={{
          position: 'absolute', bottom: 8, left: 8, right: 8,
          padding: '6px 10px', background: 'rgba(17,24,39,0.9)',
          borderRadius: 6, fontSize: 11, color: '#9ca3af',
          border: '1px solid rgba(75,85,99,0.3)',
        }}>
          公开献金节点仅表示 FEC 公开记录，不构成利益冲突判断。
        </div>
      )}
    </div>
  );
}