import { Slider } from 'antd';

interface Props {
  value: [string, string];
  onChange: (value: [string, string]) => void;
}

export default function TimeSliceControl({ value, onChange }: Props) {
  const yearToIndex = (year: number) => year - 2017;
  const indexToYear = (idx: number) => idx + 2017;

  return (
    <div style={{ padding: '4px 12px' }}>
      <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>时间范围</div>
      <Slider
        range
        min={0}
        max={9}
        defaultValue={[2, 9]}
        onChange={(vals) => {
          onChange([
            `${indexToYear(vals[0])}-01-01`,
            `${indexToYear(vals[1])}-12-31`,
          ]);
        }}
        tooltip={{
          formatter: (v?: number) => v !== undefined ? `${indexToYear(v)} 年` : '',
        }}
        style={{ margin: '0 8px' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#6b7280' }}>
        <span>2019</span>
        <span>2026</span>
      </div>
    </div>
  );
}
