import { Drawer, Tag, Descriptions, Empty, Divider } from 'antd';
import { InfoCircleOutlined, WarningOutlined, LinkOutlined } from '@ant-design/icons';
import type { EvidenceResponse } from '../../api/types';

interface Props {
  open: boolean;
  evidence: EvidenceResponse | null;
  onClose: () => void;
}

export default function EvidenceDrawer({ open, evidence, onClose }: Props) {
  return (
    <Drawer
      title="证据溯源"
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      className="evidence-drawer"
      bodyStyle={{ padding: 16 }}
    >
      {!evidence ? (
        <Empty description="暂无证据信息" />
      ) : (
        <div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Claim ID</div>
            <div style={{ fontFamily: 'monospace', fontSize: 13, color: '#1890ff' }}>
              {evidence.claim.claim_id}
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>关系类型</div>
            <Tag color="blue">{evidence.claim.relation_type}</Tag>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>置信度</div>
            <div>
              <span style={{
                fontSize: 18, fontWeight: 700,
                color: evidence.claim.confidence_score >= 0.8 ? '#52c41a'
                  : evidence.claim.confidence_score >= 0.5 ? '#faad14'
                  : '#f5222d',
              }}>
                {(evidence.claim.confidence_score * 100).toFixed(0)}%
              </span>
              {evidence.claim.confidence_score < 0.5 && (
                <Tag color="orange" icon={<WarningOutlined />} style={{ marginLeft: 8 }}>
                  需人工复核
                </Tag>
              )}
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>声明内容</div>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: '#d1d5db', background: '#1a2332', padding: 12, borderRadius: 4 }}>
              {evidence.claim.claim_text}
            </div>
          </div>

          {evidence.claim.original_snippet && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>原文片段</div>
              <div style={{ fontSize: 12, lineHeight: 1.6, color: '#9ca3af', background: '#111827', padding: 12, borderRadius: 4, fontStyle: 'italic' }}>
                {evidence.claim.original_snippet}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>审核状态</div>
            <Tag color={
              evidence.claim.review_status === 'needs_review' ? 'orange'
              : evidence.claim.review_status === 'reviewed_approved' ? 'green'
              : 'default'
            }>
              {evidence.claim.review_status}
            </Tag>
          </div>

          <Divider />

          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#e5e7eb' }}>
            证据来源 ({evidence.source_documents.length})
          </div>

          {evidence.source_documents.length === 0 ? (
            <Empty description="暂无来源文档" />
          ) : (
            evidence.source_documents.map((doc) => (
              <div key={doc.id} style={{
                marginBottom: 12, padding: 12, background: '#111827', borderRadius: 4,
                border: '1px solid #1f2937',
              }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{doc.title || doc.source_name}</div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>
                  {doc.publisher} | {doc.published_at}
                </div>
                {doc.source_url && (
                  <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 11, color: '#1890ff' }}>
                    <LinkOutlined /> {doc.source_url}
                  </a>
                )}
                {doc.snippet && (
                  <div style={{
                    fontSize: 11, color: '#6b7280', marginTop: 8, fontStyle: 'italic',
                    background: '#0a0e17', padding: 8, borderRadius: 4,
                  }}>
                    {doc.snippet}
                  </div>
                )}
                <div style={{ marginTop: 8 }}>
                  <Tag color="default" style={{ fontSize: 10 }}>{doc.source_reliability}</Tag>
                  <Tag color="default" style={{ fontSize: 10 }}>{doc.document_type}</Tag>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </Drawer>
  );
}
