import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout, Card, Tag, Button, Spin, Tabs, message, Progress, Alert, Descriptions, Empty, Typography } from 'antd';
import { ArrowLeftOutlined, FileTextOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { getMember, getMemberGraph, expandGraph, getEvidence, generateReport, predictVote, getMemberProfile } from '../api/client';
import type { MemberDetail, MemberProfileResponse, GraphResponse, EvidenceResponse, PredictionResponse } from '../api/types';
import GraphCanvas from '../components/GraphCanvas/GraphCanvas';
import EvidenceDrawer from '../components/EvidenceDrawer/EvidenceDrawer';
import ErrorBoundary from '../components/ErrorBoundary';
import { getPartyColor } from '../constants';

const { Sider, Content } = Layout;
const { Text } = Typography;

const UNAVAILABLE_MESSAGE = '暂未接入';

function UnavailablePanel({ title, reason }: { title: string; reason: string }) {
  return (
    <div style={{ padding: 16 }}>
      <Alert
        type="info"
        message={title}
        description={`${UNAVAILABLE_MESSAGE}。${reason}`}
        showIcon
        style={{ background: '#1a1a2e', border: '1px solid #1f2937' }}
      />
    </div>
  );
}

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [profile, setProfile] = useState<MemberProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

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
        getMemberGraph(id, { depth: 2, limit: 200, include_related_people: false }),
      ]);
      setMember(m);
      setGraph(g);
      try {
        const p = await predictVote({ member_id: id });
        setPrediction(p);
      } catch {
        setPrediction(null);
      }
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
    try {
      const g = await expandGraph({ node_id: nodeId, depth: 1, limit: 50 });
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

        <Card size="small" style={{ marginBottom: 12 }} bodyStyle={{ padding: 12 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%', background: getPartyColor(member.party),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 700, fontSize: 20,
            }}>
              {member.canonical_name.charAt(0)}
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{member.display_name}</div>
              <div style={{ color: '#9ca3af', fontSize: 13 }}>
                <Tag color={getPartyColor(member.party)} style={{ marginRight: 4 }}>{member.party}</Tag>
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
                  <Descriptions column={1} size="small" style={{ background: 'transparent' }} colon={false}
                    labelStyle={{ color: '#6b7280', fontSize: 11 }}
                    contentStyle={{ color: '#d1d5db', fontSize: 12 }}
                  >
                    <Descriptions.Item label="Bioguide ID">
                      <Text copyable style={{ color: '#d1d5db', fontSize: 12 }}>{member.bioguide_id || '--'}</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="GovTrack ID">
                      {member.govtrack_id || '--'}
                    </Descriptions.Item>
                    <Descriptions.Item label="FEC Candidate ID">
                      <Text copyable style={{ color: '#d1d5db', fontSize: 12 }}>{member.fec_candidate_id || '--'}</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="OpenSecrets ID">
                      {member.opensecrets_id || '--'}
                    </Descriptions.Item>
                    <Descriptions.Item label="数据来源">
                      <Tag color={member.source === 'uscl' ? 'green' : 'orange'} style={{ fontSize: 10 }}>
                        {member.source}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="任期开始">
                      {member.latest_term_start || '--'}
                    </Descriptions.Item>
                    <Descriptions.Item label="任期结束">
                      {member.latest_term_end || '--'}
                    </Descriptions.Item>
                    <Descriptions.Item label="最后更新">
                      {member.last_updated || '--'}
                    </Descriptions.Item>
                  </Descriptions>

                  {member.official_ids && Object.keys(member.official_ids).length > 0 && (
                    <Card size="small" title="Official IDs" style={{ marginTop: 12, background: '#1a1a2e' }}>
                      {Object.entries(member.official_ids).map(([k, v]) => (
                        <div key={k} style={{ marginBottom: 4 }}>
                          <Text style={{ color: '#6b7280', fontSize: 11 }}>{k}: </Text>
                          <Text style={{ color: '#d1d5db', fontSize: 11 }}>
                            {Array.isArray(v) ? (v as string[]).join(', ') : String(v)}
                          </Text>
                        </div>
                      ))}
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
                  {/* Profile status banner */}
                  {profile.profile_status !== 'available' && (
                    <Alert
                      type="warning"
                      showIcon
                      message="履历数据暂未完整接入"
                      description={
                        profile.profile_status === 'summary_only'
                          ? '当前仅展示 USCL 基础资料（姓名、党派、州、届次、委员会）。Wikipedia/Wikidata 结构化履历尚未导入。'
                          : '部分履历字段已解析，以下字段待补充: ' + (profile.missing_fields || []).join('、')
                      }
                      style={{ marginBottom: 12, background: '#1f1a10', border: '1px solid #614700' }}
                    />
                  )}

                  {/* Always show summary + basic info */}
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
                          ? '暂无摘要。本议员履历数据尚未从 Wikipedia/Wikidata 导入。'
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

                  {profile.profile_status === 'available' ? (
                    <>
                      {/* Section 2: Basic bio */}
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

                      {/* Section 3: Education */}
                      <Card size="small" title={<>教育经历 {profile.education.length === 0 && <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>(未解析)</Text>}</>}
                        style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        {profile.education.length > 0 ? (
                          profile.education.map((edu, i) => (
                            <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                              - {String(edu.institution || edu.school || edu.degree || JSON.stringify(edu))}
                            </div>
                          ))
                        ) : (
                          <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>暂未接入。待 Wikipedia 数据接入后补充。</Text>
                        )}
                      </Card>

                      {/* Section 4: Occupations + prior positions */}
                      <Card size="small" title={<>职业 / 任职经历 {profile.occupations.length === 0 && profile.prior_positions.length === 0 && <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>(未解析)</Text>}</>}
                        style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        {profile.occupations.length > 0 && (
                          <div style={{ marginBottom: 6 }}>
                            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>职业</div>
                            <div style={{ fontSize: 11, color: '#d1d5db' }}>{profile.occupations.join(', ')}</div>
                          </div>
                        )}
                        {profile.prior_positions.length > 0 && (
                          <div>
                            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>过往职位</div>
                            {profile.prior_positions.slice(0, 10).map((pos, i) => (
                              <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                                - {String(pos.position || JSON.stringify(pos))}
                              </div>
                            ))}
                          </div>
                        )}
                        {profile.occupations.length === 0 && profile.prior_positions.length === 0 && (
                          <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>暂未接入。待 Wikipedia 数据接入后补充。</Text>
                        )}
                      </Card>

                      {/* Section 5: Employers */}
                      <Card size="small" title={<>雇主机构 {profile.employers.length === 0 && <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>(未解析)</Text>}</>}
                        style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        {profile.employers.length > 0 ? (
                          profile.employers.map((emp, i) => (
                            <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                              - {String(emp.name || emp.organization || JSON.stringify(emp))}
                            </div>
                          ))
                        ) : (
                          <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>暂未接入。待 Wikipedia 数据接入后补充。</Text>
                        )}
                      </Card>

                      {/* Section 6: Military */}
                      <Card size="small" title={<>军事经历 {profile.military_service.length === 0 && <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>(未解析)</Text>}</>}
                        style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        {profile.military_service.length > 0 ? (
                          profile.military_service.map((ms, i) => (
                            <div key={i} style={{ marginBottom: 2, fontSize: 11, color: '#9ca3af' }}>
                              - {String(ms.detail || JSON.stringify(ms))}
                            </div>
                          ))
                        ) : (
                          <Text type="secondary" style={{ fontSize: 10, fontStyle: 'italic' }}>暂未接入。待 Wikipedia 数据接入后补充。</Text>
                        )}
                      </Card>

                      {/* Section 7: Source + last updated */}
                      <Card size="small" title="来源与更新时间" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                        <div style={{ fontSize: 10, color: '#6b7280' }}>
                          <div>数据来源: {profile.source === 'wikipedia' ? 'Wikipedia' : profile.source === 'fixture' ? 'Fixture (测试数据)' : 'UnitedStates/Congress-Legislators (CC0-1.0)'}</div>
                          <div>可靠度: {profile.source_reliability}</div>
                          {profile.wikidata_qid && <div>Wikidata: {profile.wikidata_qid}</div>}
                          {profile.last_updated && <div>最后更新: {profile.last_updated.replace('T', ' ').slice(0, 19)}</div>}
                        </div>
                      </Card>

                      {/* Section 8: Unresolved fields notice */}
                      {profile.missing_fields.length > 0 && (
                        <Card size="small" style={{ background: '#1a1a2e', border: '1px dashed #374151' }}>
                          <div style={{ fontSize: 10, color: '#6b7280' }}>
                            <div style={{ marginBottom: 2, fontWeight: 600, color: '#9ca3af' }}>未解析字段说明</div>
                            <div>以下字段当前未解析，待 Wikipedia API 可达后补充:</div>
                            <div style={{ marginTop: 2 }}>{profile.missing_fields.join(', ')}</div>
                          </div>
                        </Card>
                      )}
                    </>
                  ) : (
                    /* Summary-only: show USCL basic info */
                    <Card size="small" title="USCL 基础资料" style={{ marginBottom: 8, background: '#1a1a2e' }}>
                      <Descriptions column={1} size="small" colon={false}
                        labelStyle={{ color: '#6b7280', fontSize: 11 }}
                        contentStyle={{ color: '#d1d5db', fontSize: 12 }}
                      >
                        <Descriptions.Item label="已解析字段">
                          {(profile.parsed_fields || []).length > 0
                            ? profile.parsed_fields.join('、')
                            : '基本信息（姓名、党派、州、届次、委员会）'}
                        </Descriptions.Item>
                        <Descriptions.Item label="未解析字段">
                          {(profile.missing_fields || []).length > 0
                            ? profile.missing_fields.join('、')
                            : '教育、职业、任职经历、军事经历等'}
                        </Descriptions.Item>
                        <Descriptions.Item label="数据来源">
                          {profile.source === 'wikipedia' ? 'Wikipedia' : profile.source === 'wikipedia_snapshot' ? 'Wikipedia Snapshot' : profile.source === 'fixture' ? 'Fixture' : 'UnitedStates/Congress-Legislators (CC0-1.0)'}
                        </Descriptions.Item>
                      </Descriptions>
                    </Card>
                  )}
                </div>
              ) : (
                <UnavailablePanel title="履历信息" reason="需接入 Wikipedia / Ballotpedia 数据源" />
              ),
            },
            {
              key: 'contributors',
              label: '献金',
              children: (
                <UnavailablePanel title="政治献金" reason="需接入 OpenSecrets / FEC API" />
              ),
            },
            {
              key: 'holdings',
              label: '持股',
              children: (
                <UnavailablePanel title="持股披露" reason="需接入 House / Senate 财务披露数据" />
              ),
            },
            {
              key: 'china',
              label: '涉华立场',
              children: (
                <UnavailablePanel title="涉华立场分析" reason="需 NLP 分析引擎与人工标注" />
              ),
            },
            {
              key: 'controversies',
              label: '争议',
              children: (
                <UnavailablePanel title="争议与调查记录" reason="需多源新闻聚合与审核机制" />
              ),
            },
            {
              key: 'prediction',
              label: '预测',
              children: (
                <UnavailablePanel title="投票预测" reason="预测模型尚未部署" />
              ),
            },
          ]}
        />
        <Alert
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
          message="当前为基础画像报告"
          description="不包含预测分析、风险评分、利益冲突判断。献金、持股、涉华立场、争议记录暂未接入。"
          style={{ marginTop: 12, background: '#1a1a2e', border: '1px solid #1f2937', fontSize: 11 }}
        />
      </Sider>
      <Content style={{ background: '#0a0e17' }}>
        {graph && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ padding: '4px 8px', fontSize: 10, color: '#6b7280', background: '#0f1320', borderBottom: '1px solid #1f2937' }}>
              基础身份关系 + 履历事实 (教育 / 任职 / 来源)；同事网络默认隐藏。
            </div>
            <ErrorBoundary>
            <GraphCanvas
              graph={graph}
              onDoubleClickNode={handleDoubleClick}
              onEdgeClick={handleEdgeClick}
              height="100%"
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
