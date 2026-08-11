import { useState } from "react";
import { Alert, Button, Card, Col, Form, Input, List, Row, Select, Space, Tag, Typography } from "antd";
import { CheckOutlined, SearchOutlined, SwapOutlined } from "@ant-design/icons";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";
import SignalChart from "../components/SignalChart";

const { Paragraph, Text } = Typography;

export default function PolarityReviewPage() {
  const [cowId, setCowId] = useState("");
  const [loading, setLoading] = useState(false);
  const [reviews, setReviews] = useState([]);
  const [selected, setSelected] = useState(null);
  const [points, setPoints] = useState([]);
  const [hours, setHours] = useState([]);
  const [hour, setHour] = useState(null);
  const [hourPoints, setHourPoints] = useState([]);
  const [message, setMessage] = useState(null);

  const refresh = async (id) => {
    const [reviewResponse, hoursResponse] = await Promise.all([
      apiClient.get(`/polarity/${id}`), apiClient.get(`/signals/${id}/hours`),
    ]);
    setReviews(reviewResponse.data.reviews);
    setHours(hoursResponse.data.hours);
    return reviewResponse.data;
  };

  const prepare = async ({ cow_id }) => {
    setLoading(true); setCowId(cow_id); setMessage(null);
    try {
      const response = await apiClient.post(`/polarity/${cow_id}/prepare`);
      const status = await refresh(cow_id);
      setMessage({ type: status.pending_count ? "warning" : "success", text: response.data.message });
    } finally { setLoading(false); }
  };

  const openReview = async (review) => {
    setSelected(review);
    const response = await apiClient.get(`/polarity/${cowId}/${review.id}/signal`);
    setPoints(response.data.points);
  };

  const decide = async (decision) => {
    await apiClient.post(`/polarity/${cowId}/${selected.id}/decision`, null, { params: { decision } });
    const status = await refresh(cowId);
    const updated = status.reviews.find((item) => item.id === selected.id);
    setSelected(updated);
    setMessage({ type: status.pending_count ? "warning" : "success", text: status.pending_count ? `${status.pending_count} section(s) still need review.` : "All flagged sections are reviewed. Analysis is unlocked." });
  };

  const loadHour = async (value) => {
    setHour(value);
    const response = await apiClient.get(`/signals/${cowId}/hour`, { params: { start: value } });
    setHourPoints(response.data.points);
  };

  const pending = reviews.filter((review) => review.status === "pending").length;
  return (
    <>
      <PageIntro title="Polarity Review" subtitle="Review suspected continuous reversed sections before contraction analysis begins." bullets={[
        "Only automatically flagged continuous sections require approval.",
        "Each review includes 30 minutes before and after the flagged signal.",
        "The hourly browser lets you manually inspect every recorded hour, including unflagged files.",
      ]} />
      <Card className="workflow-card" title="1. Prepare review" style={{ marginBottom: 18 }}>
        <Form layout="inline" onFinish={prepare}><Form.Item name="cow_id" rules={[{ required: true }]}><Input prefix={<SearchOutlined />} placeholder="Cow ID, for example 6263" /></Form.Item><Button type="primary" htmlType="submit" loading={loading}>Screen polarity</Button></Form>
      </Card>
      {message && <Alert type={message.type} showIcon message={message.text} style={{ marginBottom: 18 }} />}
      {cowId && <Row gutter={[18, 18]}>
        <Col xs={24} lg={8}><Card title={`2. Flagged sections (${reviews.length})`} extra={<Tag color={pending ? "gold" : "green"}>{pending} pending</Tag>}><List dataSource={reviews} locale={{ emptyText: "No reversed sections were detected" }} renderItem={(review) => <List.Item onClick={() => openReview(review)} className={`review-list-item ${selected?.id === review.id ? "selected" : ""}`}><List.Item.Meta title={<Space><Text>{new Date(review.start_time).toLocaleString()}</Text><Tag color={review.status === "pending" ? "gold" : review.status === "flip" ? "purple" : "green"}>{review.status}</Tag></Space>} description={`${review.first_source_file} → ${review.last_source_file}`} /></List.Item>} /></Card></Col>
        <Col xs={24} lg={16}><Card title="3. Review signal with context">{selected ? <><Paragraph>{selected.reason}</Paragraph><Paragraph><Text strong>Detected interval: </Text>{new Date(selected.start_time).toLocaleString()} to {new Date(selected.end_time).toLocaleString()}</Paragraph><div className="context-legend"><span>30-minute before context</span><strong>Shaded: detected possible reversal</strong><span>30-minute after context</span></div><SignalChart points={points} highlightStart={selected.start_time} highlightEnd={selected.end_time} /><Space wrap><Button icon={<CheckOutlined />} onClick={() => decide("keep")}>Keep polarity</Button><Button type="primary" icon={<SwapOutlined />} onClick={() => decide("flip")}>Flip section</Button><Button danger onClick={() => decide("uncertain")}>Uncertain / exclude</Button></Space></> : <Alert type="info" message="Select a flagged section to review it." />}</Card></Col>
        <Col span={24}><Card title="Manual hourly contraction browser" extra={<Text type="secondary">Inspect every hour for missed reversals</Text>}><Space wrap style={{ marginBottom: 16 }}><Select showSearch value={hour} onChange={loadHour} placeholder="Select a recorded hour" style={{ minWidth: 280 }} options={hours.map((value) => ({ value, label: new Date(value).toLocaleString() }))} /><Tag color="brown">{hourPoints.length} displayed points</Tag></Space>{hour ? <SignalChart points={hourPoints} /> : <Alert type="info" message="Choose an hour to inspect the contraction and movement signals." />}</Card></Col>
      </Row>}
    </>
  );
}
