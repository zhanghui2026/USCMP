import { useEffect, useState } from 'react';
import { Layout, Card, Statistic, Row, Col, Table, Tag, Spin, Typography } from 'antd';
import {
  DatabaseOutlined, NodeIndexOutlined, ApartmentOutlined,
  WarningOutlined, ExclamationCircleOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import { getDataQuality } from '../api/client';
import type { DataQualitySummaryResponse } from '../api/types';
import { DATA_MODE_COLORS, DATA_MODE_LABELS } from '../constants';

const { Content } = Layout;
const { Title } = Typography;

export default function DataQualityPage() {
  const [dq, setDq] = useState<DataQualitySummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await getDataQuality();
      setDq(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />;
  if (!dq) return <div style={{ padding: 24, color: '#9ca3af' }}>加载失败</div>;

  const distToTable = (dist: Record<string, number> | undefined) => {
    if (!dist) return [];
    return Object.entries(dist).map(([key, value]) => ({ key, value }));
  };

  return (
    <Layout style={{ height: '100%', background: 'transparent' }}>
      <Content style={{ padding: 24, overflow: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>数据质量总览</Title>
          <Tag color={DATA_MODE_COLORS[dq.data_mode] || 'default'} style={{ fontSize: 14, padding: '4px 12px' }}>
            {DATA_MODE_LABELS[dq.data_mode] || dq.data_mode}
          </Tag>
        </div>

        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic title="图谱节点" value={dq.total_nodes} prefix={<NodeIndexOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic title="图谱边" value={dq.total_edges} prefix={<ApartmentOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic title="Claims" value={dq.total_claims} prefix={<DatabaseOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic title="Source Documents" value={dq.total_source_documents} prefix={<CheckCircleOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic
                title="低置信度边"
                value={dq.low_confidence_edges}
                prefix={<WarningOutlined />}
                valueStyle={{ color: dq.low_confidence_edges > 0 ? '#faad14' : '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8} md={6} lg={4}>
            <Card>
              <Statistic
                title="待审查 Claims"
                value={dq.needs_review_claims}
                prefix={<ExclamationCircleOutlined />}
                valueStyle={{ color: dq.needs_review_claims > 0 ? '#ff4d4f' : '#52c41a' }}
              />
            </Card>
          </Col>
        </Row>

        {dq.sandbox_persons > 0 && (
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col span={24}>
              <Title level={5} style={{ marginBottom: 12, color: '#08979c' }}>
                沙盒数据 (Sandbox) - unitedstates/congress-legislators
              </Title>
            </Col>
            <Col xs={12} sm={8} md={6} lg={4}>
              <Card>
                <Statistic title="真实议员" value={dq.sandbox_persons} prefix={<NodeIndexOutlined />} />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={6} lg={4}>
              <Card>
                <Statistic title="Sandbox Claims" value={dq.sandbox_claims} prefix={<DatabaseOutlined />} />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={6} lg={4}>
              <Card>
                <Statistic title="Sandbox Source Docs" value={dq.sandbox_source_documents} prefix={<CheckCircleOutlined />} />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={6} lg={4}>
              <Card>
                <Statistic
                  title="安全匹配"
                  value={dq.sandbox_entity_resolution_safe}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} md={6} lg={4}>
              <Card>
                <Statistic
                  title="需审查"
                  value={dq.sandbox_entity_resolution_needs_review}
                  prefix={<ExclamationCircleOutlined />}
                  valueStyle={{ color: dq.sandbox_entity_resolution_needs_review > 0 ? '#ff4d4f' : '#52c41a' }}
                />
              </Card>
            </Col>
          </Row>
        )}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card title="节点类型分布" size="small">
              <Table
                dataSource={distToTable(dq.node_type_distribution)}
                columns={[
                  { title: '类型', dataIndex: 'key', key: 'key' },
                  { title: '数量', dataIndex: 'value', key: 'value' },
                ]}
                rowKey="key"
                size="small"
                pagination={false}
              />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="边类型分布" size="small">
              <Table
                dataSource={distToTable(dq.edge_type_distribution)}
                columns={[
                  { title: '类型', dataIndex: 'key', key: 'key' },
                  { title: '数量', dataIndex: 'value', key: 'value' },
                ]}
                rowKey="key"
                size="small"
                pagination={false}
              />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="Source Reliability 分布" size="small">
              <Table
                dataSource={distToTable(dq.source_reliability_distribution)}
                columns={[
                  { title: '来源', dataIndex: 'key', key: 'key' },
                  { title: '数量', dataIndex: 'value', key: 'value' },
                ]}
                rowKey="key"
                size="small"
                pagination={false}
              />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="Extraction Method 分布" size="small">
              <Table
                dataSource={distToTable(dq.extraction_method_distribution)}
                columns={[
                  { title: '方法', dataIndex: 'key', key: 'key' },
                  { title: '数量', dataIndex: 'value', key: 'value' },
                ]}
                rowKey="key"
                size="small"
                pagination={false}
              />
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
