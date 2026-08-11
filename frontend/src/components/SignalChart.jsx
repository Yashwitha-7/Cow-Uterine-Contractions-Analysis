import { useMemo, useState } from "react";
import { Button, Modal, Segmented, Slider, Space, Typography } from "antd";
import { ExpandOutlined } from "@ant-design/icons";

const { Text } = Typography;

function Chart({ points, field, zoom, highlightStart, highlightEnd }) {
  const visible = useMemo(() => {
    if (!points.length) return [];
    const start = Math.floor((zoom[0] / 100) * (points.length - 1));
    const end = Math.max(start + 2, Math.ceil((zoom[1] / 100) * points.length));
    return points.slice(start, end);
  }, [points, zoom]);
  const values = visible.map((point) => Number(point[field])).filter(Number.isFinite);
  if (!values.length) return <div className="empty-chart">No signal values in this interval</div>;
  const tickIndexes = Array.from(new Set([0, 0.25, 0.5, 0.75, 1].map(
    (fraction) => Math.round(fraction * (visible.length - 1))
  )));
  const formatTime = (value) => new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const zeroY = 250 - ((0 - min) / range) * 220;
  const firstTime = new Date(visible[0].timestamp_corrected).getTime();
  const lastTime = new Date(visible[visible.length - 1].timestamp_corrected).getTime();
  const visibleDuration = Math.max(lastTime - firstTime, 1);
  const highlightLeft = highlightStart
    ? Math.max(0, Math.min(100, ((new Date(highlightStart).getTime() - firstTime) / visibleDuration) * 100))
    : null;
  const highlightRight = highlightEnd
    ? Math.max(0, Math.min(100, ((new Date(highlightEnd).getTime() - firstTime) / visibleDuration) * 100))
    : null;
  const path = visible.map((point, index) => {
    const value = Number(point[field]);
    const x = (index / Math.max(visible.length - 1, 1)) * 1000;
    const y = 250 - ((value - min) / range) * 220;
    return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <div className="signal-chart-wrap">
      {highlightLeft !== null && highlightRight !== null && highlightRight > highlightLeft && (
        <div
          className="flagged-region"
          style={{ left: `calc(8px + (100% - 50px) * ${highlightLeft / 100})`, width: `calc((100% - 50px) * ${(highlightRight - highlightLeft) / 100})` }}
        >
          <span>Detected possible reversal</span>
        </div>
      )}
      <svg className="signal-chart" viewBox="0 0 1000 280" preserveAspectRatio="none" role="img" aria-label="Interactive contraction strain signal">
        <line x1="0" y1={zeroY} x2="1000" y2={zeroY} className="zero-axis-line" />
        <path d={path} className="signal-line" />
      </svg>
      <div className="time-axis" aria-label="Signal time axis">
        {tickIndexes.map((index) => (
          <span key={`${visible[index].timestamp_corrected}-${index}`}>
            {formatTime(visible[index].timestamp_corrected)}
          </span>
        ))}
      </div>
      <div className="chart-scale">
        <span className="scale-max">{max.toFixed(2)}</span>
        <span className="zero-label" style={{ top: `${(zeroY / 280) * 100}%` }}>0</span>
        <span className="scale-min">{min.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function SignalChart({ points = [], defaultField = "strain_centered_file", highlightStart = null, highlightEnd = null }) {
  const [field, setField] = useState(defaultField);
  const [zoom, setZoom] = useState([0, 100]);
  const [expanded, setExpanded] = useState(false);
  const content = (
    <>
      <Space wrap className="chart-controls">
        <Segmented value={field} onChange={setField} options={[
          { label: "Centered strain", value: "strain_centered_file" },
          { label: "Raw strain", value: "strain" },
          { label: "Acceleration", value: "acc_magnitude" },
          { label: "Gyroscope", value: "gyro_magnitude" },
        ]} />
        <Text type="secondary">Drag the range handles to inspect a smaller part of the hour.</Text>
      </Space>
      <Chart points={points} field={field} zoom={zoom} highlightStart={highlightStart} highlightEnd={highlightEnd} />
      <Slider range value={zoom} onChange={setZoom} tooltip={{ formatter: (value) => `${value}%` }} />
    </>
  );
  return (
    <>
      <div className="signal-toolbar"><Button icon={<ExpandOutlined />} onClick={() => setExpanded(true)}>Expand signal</Button></div>
      {content}
      <Modal open={expanded} onCancel={() => setExpanded(false)} footer={null} width="96vw" title="Expanded hourly signal review">
        {content}
      </Modal>
    </>
  );
}
