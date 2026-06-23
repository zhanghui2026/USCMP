import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout, Card, Tag, Button, Spin, Tabs, message, Descriptions, Empty, Typography } from 'antd';
import { ArrowLeftOutlined, FileTextOutlined } from '@ant-design/icons';
import { getMember, getMemberGraph, expandGraph, getEvidence, generateReport, getMemberProfile } from '../api/client';
import type { MemberDetail, MemberProfileResponse, GraphResponse, EvidenceResponse, CircleResponse, CircleMember, CircleExpandResponse } from '../api/types';
import GraphCanvas from '../components/GraphCanvas/GraphCanvas';
import EvidenceDrawer from '../components/EvidenceDrawer/EvidenceDrawer';
import ErrorBoundary from '../components/ErrorBoundary';
import MemberAvatar from '../components/MemberAvatar';
import ControversiesTab from '../components/ControversiesTab';
import ContributionsTab from '../components/ContributionsTab';
import HoldingsTab from '../components/HoldingsTab';
import ProfileTab from '../components/ProfileTab';

const { Sider, Content } = Layout;
const { Text } = Typography;

const UNAVAILABLE_MESSAGE = '暂未接入';

function PlaceholderTab() {
  return (
    <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
      {UNAVAILABLE_MESSAGE}
    </div>
  );
}

function CirclesPanel({ memberId, onCircleClick, onMemberClick }: { memberId: string; onCircleClick?: (circleType: string) => void; onMemberClick?: (memberId: string) => void }) {
  const [data, setData] = useState<CircleResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedMembers, setExpandedMembers] = useState<CircleMember[]>([]);
  const [loadingExpand, setLoadingExpand] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { getMemberCircles } = await import('../api/client');
        const res = await getMemberCircles(memberId);
        setData(res);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [memberId]);

  const handleExpand = async (circleType: string) => {
    if (expanded === circleType) {
      setExpanded(null);
      setExpandedMembers([]);
      return;
    }
    setLoadingExpand(true);
    setExpanded(circleType);
    try {
      const { getCircleMembers } = await import('../api/client');
      const res = await getCircleMembers(memberId, circleType);
      setExpandedMembers(res.members || []);
    } catch {
      setExpandedMembers([]);
    } finally {
      setLoadingExpand(false);
    }
  };

  const strengthColor: Record<string, string> = {
    strong: '#52c41a',
    medium: '#faad14',
    weak: '#8c8c8c',
  };
  const strengthLabel: Record<string, string> = {
    strong: '强关联',
    medium: '中关联',
    weak: '弱关联',
  };

  if (loading) return <Spin style={{ display: 'block', margin: '40px auto' }} />;
  if (!data || data.categories.length === 0) {
    return <Empty description="暂无共同背景数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div>
      {data.categories.map((cat) => (
        <Card
          key={cat.circle_type}
          size="small"
          title={cat.circle_name}
          style={{ marginBottom: 8, background: '#1a1a2e', cursor: 'pointer' }}
          onClick={() => {
            handleExpand(cat.circle_type);
            onCircleClick?.(cat.circle_type);
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <Tag color={strengthColor[cat.strength_level] || '#8c8c8c'} style={{ fontSize: 10, margin: 0 }}>
              {strengthLabel[cat.strength_level] || cat.strength_level}
            </Tag>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>
              关联 {cat.related_count} 人
            </span>
          </div>
          <div style={{ fontSize: 10, color: '#6b7280' }}>
            证据: {cat.evidence_type} | 来源: {cat.source}
            {cat.source_url && <span> | <a href={cat.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff' }}>链接</a></span>}
          </div>

          {expanded === cat.circle_type && (
            <div style={{ marginTop: 8, borderTop: '1px solid #1f2937', paddingTop: 8 }}>
              {loadingExpand ? (
                <Spin size="small" style={{ display: 'block', margin: '8px auto' }} />
              ) : expandedMembers.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 11, fontStyle: 'italic' }}>暂无关联</Text>
              ) : (
                expandedMembers.slice(0, 20).map((m) => (
                  <div
                    key={m.member_id}
                    onClick={(e) => { e.stopPropagation(); onMemberClick?.(m.member_id); }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: 12, cursor: 'pointer', borderRadius: 6, padding: '4px 6px' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#1f2937'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <MemberAvatar display_name={m.display_name} party={m.party} size={24} />
                    <div>
                      <div style={{ color: '#d1d5db' }}>{m.display_name}</div>
                      <div style={{ color: '#6b7280', fontSize: 10 }}>
                        {m.party} | {m.state} | 关联: {m.shared_via}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [profile, setProfile] = useState<MemberProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [addedNodeIds, setAddedNodeIds] = useState<Map<string, string[]>>(new Map());
  const [addedEdgeIds, setAddedEdgeIds] = useState<Map<string, string[]>>(new Map());

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [m, g] = await Promise.all([
        getMember(id),
        getMemberGraph(id, {
          depth: 2,
          limit: 200,
          include_related_people: false,
          include_finance: true,
          include_holdings: true,
        }),
      ]);
      setMember(m);
      setGraph(g);
      try {
        const prof = await getMemberProfile(id);
        setProfile(prof);
      } catch {
        setProfile(null);
      }
    } catch (e) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDoubleClick = async (nodeId: string) => {
    if (!graph) return;

    // If already expanded, collapse it
    if (expandedNodes.has(nodeId)) {
      const rmNodeIds = addedNodeIds.get(nodeId) || [];
      const rmEdgeIds = addedEdgeIds.get(nodeId) || [];
      const nodeSet = new Set(rmNodeIds);
      const edgeSet = new Set(rmEdgeIds);
      setGraph({
        ...graph,
        nodes: graph.nodes.filter((n) => !nodeSet.has(n.id)),
        edges: graph.edges.filter((e) => !edgeSet.has(e.id)),
      });
      const next = new Set(expandedNodes);
      next.delete(nodeId);
      setExpandedNodes(next);

      const nextNodes = new Map(addedNodeIds);
      nextNodes.delete(nodeId);
      setAddedNodeIds(nextNodes);
      const nextEdges = new Map(addedEdgeIds);
      nextEdges.delete(nodeId);
      setAddedEdgeIds(nextEdges);
      return;
    }

    try {
      const g = await expandGraph({
        node_id: nodeId,
        depth: 1,
        limit: 50,
        include_finance: true,
        include_holdings: true,
      });
      if (graph) {
        const existingIds = new Set(graph.nodes.map((n) => n.id));
        const newNodes = g.nodes.filter((n) => !existingIds.has(n.id));
        const existingEdgeIds = new Set(graph.edges.map((e) => e.id));
        const newEdges = g.edges.filter((e) => !existingEdgeIds.has(e.id));
        setGraph({
          ...graph,
          nodes: [...graph.nodes, ...newNodes],
          edges: [...graph.edges, ...newEdges],
        });
        setExpandedNodes(new Set([...expandedNodes, nodeId]));
        setAddedNodeIds(new Map([...addedNodeIds, [nodeId, newNodes.map((n) => n.id)]]));
        setAddedEdgeIds(new Map([...addedEdgeIds, [nodeId, newEdges.map((e) => e.id)]]));
      }
    } catch (e) {
      message.warning('展开节点失败');
    }
  };

  const handleEdgeClick = async (claimId: string) => {
    try {
      const ev = await getEvidence(claimId);
      setEvidence(ev);
      setDrawerOpen(true);
    } catch (e) {
      message.warning('获取证据失败');
    }
  };

  const handleCircleClick = async (circleType: string) => {
    if (!graph || !id) return;
    const labelMap: Record<string, string> = {
      education: 'EducationInstitution',
      committee: 'Committee',
      state: 'State',
      party: 'Party',
      occupation: 'Position',
      employer: 'Employer',
    };
    const targetLabel = labelMap[circleType];
    if (!targetLabel) return;
    const entityNode = graph.nodes.find((n) => n.label === targetLabel);
    if (!entityNode) return;
    await handleDoubleClick(entityNode.id);
  };

  const handleExportMarkdown = async () => {
    if (!id) return;
    try {
      const report = await generateReport({
        member_id: id,
        format: 'markdown',
        include_graph: true,
        include_predictions: false,
      });
      const blob = new Blob([report.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${member?.canonical_name || 'report'}.md`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('简报已导出');
    } catch (e) {
      message.error('导出失败');
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />;
  if (!member) return <div style={{ padding: 24, color: '#9ca3af' }}>议员未找到</div>;

  return (
    <ErrorBoundary>
    <Layout style={{ height: '100%', background: 'transparent' }}>
      <Sider width={420} style={{ background: '#111827', borderRight: '1px solid #1f2937', overflow: 'auto', padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>返回</Button>
          <Button type="primary" icon={<FileTextOutlined />} onClick={handleExportMarkdown} size="small">
            导出简报
          </Button>
        </div>

        <Card size="small" style={{ marginBottom: 12 }} styles={{ body: { padding: 12 } }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <MemberAvatar image_url={profile?.image_url} display_name={member.display_name} party={member.party} size={48} />
            <div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{member.display_name}</div>
              <div style={{ color: '#9ca3af', fontSize: 13 }}>
                <Tag color={member.party === 'Republican' ? '#f5222d' : member.party === 'Democratic' ? '#1890ff' : '#8c8c8c'} style={{ marginRight: 4 }}>{member.party}</Tag>
                {member.state} | {member.chamber === 'senate' ? '参议院' : '众议院'} | 第{member.congress}届
              </div>
              <div style={{ marginTop: 4 }}>
                {member.source === 'uscl' ? (
                  <Tag color="green" style={{ fontSize: 10 }}>真实数据 (USCL)</Tag>
                ) : member.source === 'mock' ? (
                  <Tag color="orange" style={{ fontSize: 10 }}>Mock 数据</Tag>
                ) : (
                  <Tag color="default" style={{ fontSize: 10 }}>{member.source}</Tag>
                )}
              </div>
            </div>
          </div>
        </Card>

        <Tabs
          size="small"
          items={[
            {
              key: 'info',
              label: '基本信息',
              children: (
                <div style={{ fontSize: 12 }}>
                  <Card size="small" style={{ marginBottom: 8, background: '#1a1a2e' }} styles={{ body: { padding: 12 } }}>
                    <Descriptions column={1} size="small" colon={false}
                      labelStyle={{ color: '#6b7280', fontSize: 11, paddingBottom: 6 }}
                      contentStyle={{ color: '#d1d5db', fontSize: 12, paddingBottom: 6 }}
                    >
                      <Descriptions.Item label="中文名">
                        {member.canonical_name ? (
                          <Text style={{ color: '#e5e7eb', fontSize: 14, fontWeight: 600 }}>{member.canonical_name}</Text>
                        ) : member.display_name}
                      </Descriptions.Item>
                      <Descriptions.Item label="英文名">
                        {member.display_name}
                      </Descriptions.Item>
                      <Descriptions.Item label="出生日期">
                        {profile?.birth_date || <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>未收录</Text>}
                      </Descriptions.Item>
                      <Descriptions.Item label="现任职位">
                        {member.chamber === 'senate' ? '参议员' : member.chamber === 'house' ? '众议员' : member.chamber || '--'}
                      </Descriptions.Item>
                      <Descriptions.Item label="所属政党">
                        <Tag color={member.party === 'Republican' ? '#f5222d' : member.party === 'Democratic' ? '#1890ff' : '#8c8c8c'} style={{ fontSize: 11 }}>
                          {member.party === 'Democratic' ? '民主党' : member.party === 'Republican' ? '共和党' : member.party || '--'}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="所属州">
                        {member.state || '--'}
                      </Descriptions.Item>
                      <Descriptions.Item label="任期">
                        {member.latest_term_start || '--'} ~ {member.latest_term_end || '至今'}
                        <span style={{ color: '#6b7280', marginLeft: 4 }}>（第 {member.congress} 届）</span>
                      </Descriptions.Item>
                      <Descriptions.Item label="数据来源">
                        {profile?.wikipedia_url ? (
                          <a href={profile.wikipedia_url} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff', fontSize: 11 }}>
                            Wikipedia 履历 ↗
                          </a>
                        ) : member.source === 'uscl' && member.bioguide_id ? (
                          <a href={`https://bioguide.congress.gov/search/bio/${member.bioguide_id}`} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff', fontSize: 11 }}>
                            UnitedStates/Congress-Legislators (CC0-1.0) ↗
                          </a>
                        ) : (
                          <Tag color={member.source === 'uscl' ? 'green' : 'orange'} style={{ fontSize: 10 }}>
                            {member.source}
                          </Tag>
                        )}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>

                  {profile?.short_summary && (
                    <Card size="small" title="简介" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                      <div style={{ color: '#9ca3af', fontSize: 11, lineHeight: 1.7 }}>
                        {profile.short_summary.slice(0, 600)}{profile.short_summary.length > 600 && '...'}
                      </div>
                    </Card>
                  )}
                </div>
              ),
            },
            {
              key: 'committees',
              label: '委员会',
              children: (
                <div>
                  {member.committee_memberships.length === 0 ? (
                    <Empty description="暂无委员会任职记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    member.committee_memberships.map((cm, i) => (
                      <Card key={i} size="small" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{cm.committee}</div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>
                          <Tag color="purple" style={{ fontSize: 10 }}>{cm.role}</Tag>
                          <Tag style={{ fontSize: 10 }}>第 {cm.congress} 届</Tag>
                          {cm.committee_type && <Tag style={{ fontSize: 10 }}>{cm.committee_type}</Tag>}
                        </div>
                        {(cm.start_date || cm.end_date) && (
                          <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                            {cm.start_date && `${cm.start_date} `}
                            {cm.start_date && cm.end_date && '~ '}
                            {cm.end_date || '至今'}
                          </div>
                        )}
                      </Card>
                    ))
                  )}
                </div>
              ),
            },
            {
              key: 'career',
              label: '履历',
              children: profile ? (
                <div style={{ fontSize: 12 }}>
                  {/* Profile status banner: compact for summary_only */}
                  {profile.profile_status === 'summary_only' && (
                    <div style={{ marginBottom: 12, padding: '6px 10px', background: '#1f1a10', border: '1px solid #614700', borderRadius: 6, fontSize: 11, color: '#d1d5db' }}>
                      当前仅展示 USCL 基础资料，Wikipedia 结构化履历尚未导入。
                    </div>
                  )}

                  {/* Summary card */}
                  <Card size="small" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <Text strong style={{ color: '#d1d5db', fontSize: 13 }}>摘要</Text>
                      <Tag color={profile.source === 'wikipedia' ? 'blue' : profile.source === 'fixture' ? 'green' : profile.source === 'wikipedia_snapshot' ? 'cyan' : 'orange'} style={{ fontSize: 10 }}>
                        {profile.source === 'wikipedia' ? 'Wikipedia 履历' : profile.source === 'fixture' ? 'Fixture 履历' : profile.source === 'wikipedia_snapshot' ? 'Wikipedia Snapshot' : 'USCL 基础资料'}
                      </Tag>
                    </div>
                    {profile.short_summary ? (
                      <div style={{ color: '#9ca3af', fontSize: 11, lineHeight: 1.6 }}>
                        {profile.short_summary.slice(0, 500)}{profile.short_summary.length > 500 && '...'}
                      </div>
                    ) : (
                      <Text type="secondary" style={{ fontSize: 11, fontStyle: 'italic' }}>
                        {profile.profile_status === 'summary_only'
                          ? '暂无摘要。Wikipedia 结构化履历尚未导入。'
                          : '未解析'}
                      </Text>
                    )}
                    {profile.wikipedia_url && (
                      <div style={{ marginTop: 4 }}>
                        <a href={profile.wikipedia_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: '#1890ff' }}>
                          {profile.wikipedia_url}
                        </a>
                      </div>
                    )}
                  </Card>

                  {/* Basic bio */}
                  <Card size="small" title="基本履历" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                    <Descriptions column={1} size="small" colon={false}
                      labelStyle={{ color: '#6b7280', fontSize: 11 }}
                      contentStyle={{ color: '#d1d5db', fontSize: 12 }}
                    >
                      <Descriptions.Item label="出生日期">
                        {profile.birth_date || <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>未解析</Text>}
                      </Descriptions.Item>
                      <Descriptions.Item label="出生地">
                        {profile.birth_place || <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>未解析</Text>}
                      </Descriptions.Item>
                      <Descriptions.Item label="Wikidata">
                        {profile.wikidata_qid || <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>--</Text>}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>

                  {/* Education */}
                  <Card size="small" title="教育经历" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                    {profile.education.length > 0 ? (
                      profile.education.map((edu, i) => (
                        <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                          - {String(edu.institution || edu.school || edu.degree || JSON.stringify(edu))}
                        </div>
                      ))
                    ) : (
                      <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>{UNAVAILABLE_MESSAGE}</Text>
                    )}
                  </Card>

                  {/* Career highlights from Wikipedia profile */}
                  {profile.career_highlights && profile.career_highlights.length > 0 && (
                    <Card size="small" title="履历亮点" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                      {profile.career_highlights.slice(0, 10).map((hl, i) => (
                        <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                          - {String(hl.title || JSON.stringify(hl))}
                        </div>
                      ))}
                    </Card>
                  )}

                  {/* Career summary from member record */}
                  {member.career_summary && member.career_summary.length > 0 && (
                    <Card size="small" title="职业经历汇总" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                      {member.career_summary.map((item, i) => {
                        const entry = item as Record<string, unknown>;
                        const source = entry.source ? String(entry.source) : null;
                        const careerHistory = entry.career_history ? String(entry.career_history) : null;
                        const policyPositions = entry.policy_positions ? String(entry.policy_positions) : null;
                        const pos = entry.position ? String(entry.position) : null;
                        const org = entry.organization ? String(entry.organization) : null;
                        const start = entry.start_date ? String(entry.start_date) : null;
                        const end = entry.end_date ? String(entry.end_date) : null;

                        // New format from congress profiles
                        if (source === 'congress_profile') {
                          return (
                            <div key={i} style={{ marginBottom: 8 }}>
                              {careerHistory && (
                                <div style={{ marginBottom: 6 }}>
                                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>政治生涯</div>
                                  <div style={{ fontSize: 11, color: '#9ca3af', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                                    {careerHistory.replace(/\*\*/g, '').slice(0, 800)}{careerHistory.length > 800 && '...'}
                                  </div>
                                </div>
                              )}
                              {policyPositions && (
                                <div>
                                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>政策立场</div>
                                  <div style={{ fontSize: 11, color: '#9ca3af', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                                    {policyPositions.replace(/\*\*/g, '').slice(0, 800)}{policyPositions.length > 800 && '...'}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        }

                        // Legacy format
                        return (
                          <div key={i} style={{ marginBottom: 4, fontSize: 11, color: '#9ca3af' }}>
                            {pos && <span style={{ color: '#d1d5db' }}>{pos}</span>}
                            {org && <span> @ {org}</span>}
                            {(start || end) && (
                              <span style={{ color: '#6b7280', marginLeft: 4 }}>
                                ({start || ''} ~ {end || '至今'})
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </Card>
                  )}

                  {/* Career: merged occupations + prior positions + employers + military */}
                  <Card size="small" title="职业与公共任职经历" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                    {profile.occupations.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>职业</div>
                        <div style={{ fontSize: 11, color: '#d1d5db' }}>{profile.occupations.join(', ')}</div>
                      </div>
                    )}
                    {profile.prior_positions.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>过往职位</div>
                        {profile.prior_positions.slice(0, 10).map((pos, i) => (
                          <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                            - {String(pos.position || JSON.stringify(pos))}
                          </div>
                        ))}
                      </div>
                    )}
                    {profile.employers.length > 0 && (
                      <div style={{ marginBottom: 6 }}>
                        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>任职机构</div>
                        {profile.employers.map((emp, i) => (
                          <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                            - {String(emp.name || emp.organization || JSON.stringify(emp))}
                          </div>
                        ))}
                      </div>
                    )}
                    {profile.military_service.length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>军事经历</div>
                        {profile.military_service.map((ms, i) => (
                          <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                            - {String(ms.detail || JSON.stringify(ms))}
                          </div>
                        ))}
                      </div>
                    )}
                    {profile.occupations.length === 0 && profile.prior_positions.length === 0 &&
                     profile.employers.length === 0 && profile.military_service.length === 0 && (
                      <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>{UNAVAILABLE_MESSAGE}</Text>
                    )}
                  </Card>

                  {/* Source info */}
                  {(profile.profile_status === 'available' || Object.keys(profile.profile_sources || {}).length > 0) && (
                    <Card size="small" title="来源与更新时间" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                      <div style={{ fontSize: 10, color: '#6b7280' }}>
                        <div>数据来源: {profile.source === 'wikipedia' ? 'Wikipedia' : profile.source === 'fixture' ? 'Fixture (测试数据)' : 'UnitedStates/Congress-Legislators (CC0-1.0)'}</div>
                        <div>可靠度: {profile.source_reliability}</div>
                        {profile.wikidata_qid && <div>Wikidata: {profile.wikidata_qid}</div>}
                        {profile.last_updated && <div>最后更新: {profile.last_updated.replace('T', ' ').slice(0, 19)}</div>}
                        {profile.profile_sources && Object.keys(profile.profile_sources).length > 0 && (
                          <div style={{ marginTop: 6 }}>
                            {Object.entries(profile.profile_sources).map(([k, v]) => {
                              const val = String(v);
                              return (
                                <div key={k} style={{ marginBottom: 2 }}>
                                  {k}: {val.startsWith('http') ? (
                                    <a href={val} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff', wordBreak: 'break-all' }}>{val}</a>
                                  ) : (
                                    <span>{val}</span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {profile.parsed_fields && profile.parsed_fields.length > 0 && (
                          <div style={{ marginTop: 6 }}>
                            <span>已解析字段: </span>
                            <span style={{ color: '#9ca3af' }}>{profile.parsed_fields.join(', ')}</span>
                          </div>
                        )}
                      </div>
                    </Card>
                  )}
                </div>
              ) : (
                <PlaceholderTab />
              ),
            },
            {
              key: 'circles',
              label: '圈层关系',
              children: <CirclesPanel memberId={id!} onCircleClick={handleCircleClick} onMemberClick={(mid) => navigate(`/member/${mid}`)} />,
            },
            {
              key: 'profile',
              label: '政治画像',
              children: (
                <ProfileTab
                  china_stance_summary={member.china_stance_summary}
                  core_positions={member.core_positions}
                  comprehensive_evaluation={member.comprehensive_evaluation}
                />
              ),
            },
            {
              key: 'contributors',
              label: '献金',
              children: <ContributionsTab memberId={id!} />,
            },
            {
              key: 'holdings',
              label: '持股',
              children: <HoldingsTab memberId={id!} />,
            },
            {
              key: 'contentious',
              label: '媒体争议',
              children: <ControversiesTab controversies={member.controversies} />,
            },
            {
              key: 'interest',
              label: '利益链条',
              children: <PlaceholderTab />,
            },
          ]}
        />
      </Sider>
      <Content style={{ background: '#0a0e17' }}>
        {graph && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ padding: '4px 8px', fontSize: 10, color: '#6b7280', background: '#0f1320', borderBottom: '1px solid #1f2937' }}>
              身份关系 + 履历事实图谱；同事网络默认隐藏。
            </div>
            <ErrorBoundary>
            <GraphCanvas
              graph={graph}
              onDoubleClickNode={handleDoubleClick}
              onEdgeClick={handleEdgeClick}
              height="100%"
              personImages={profile?.image_url ? { [id!]: profile.image_url } : {}}
            />
            </ErrorBoundary>
          </div>
        )}
      </Content>
      <EvidenceDrawer
        open={drawerOpen}
        evidence={evidence}
        onClose={() => setDrawerOpen(false)}
      />
    </Layout>
    </ErrorBoundary>
  );
}
