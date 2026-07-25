import { useState } from "react";
import { Alert, Button, Card, Form, Input, InputNumber, Typography } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";
import OutputFileList from "../components/OutputFileList";

const { Paragraph, Text } = Typography;

export default function Phase3ProcessingPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [files, setFiles] = useState([]);
  const [cowId, setCowId] = useState("");

  const loadFiles = async (id) => {
    const response = await apiClient.get(`/files/${id}`);
    setFiles(response.data.files);
  };

  const onFinish = async (values) => {
    setLoading(true);
    setCowId(values.cow_id);

    try {
      const response = await apiClient.post(`/process/phase3/${values.cow_id}`, null, {
        params: {
          patch_offset_minutes: values.patch_offset_minutes || 0,
          bolus_offset_minutes: values.bolus_offset_minutes || 0,
        },
      });

      setResult(response.data);
      await loadFiles(values.cow_id);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageIntro
        title="Phase 3 Processing"
        subtitle="This page runs the signal preprocessing and candidate contraction event pipeline."
        bullets={[
          "Creates baseline-corrected strain and orientation-corrected strain.",
          "Computes acceleration magnitude, gyroscope magnitude, and movement artifact score.",
          "Detects candidate contraction peaks using prominence-based peak detection.",
          "Creates 10-minute summaries for bolus synchronization.",
          "If bolus data exists, creates all-bolus and overlap-only merged files.",
        ]}
      />

      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="Candidate events are not confirmed contractions."
        description="They are algorithmically detected strain peaks labeled using movement and flat-signal checks. Manual review is still required."
      />

      <Card title="Run Phase 3" style={{ marginBottom: 16 }}>
        <Paragraph>
          Run this after uploading contraction data and, if available, bolus data.
          Output files are saved automatically into <Text code>data/processed/cow_&lt;id&gt;/</Text>.
        </Paragraph>

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="6263" />
          </Form.Item>

          <Form.Item
            label="Patch offset minutes"
            name="patch_offset_minutes"
            initialValue={0}
          >
            <InputNumber step={0.1} />
          </Form.Item>

          <Form.Item
            label="Bolus offset minutes"
            name="bolus_offset_minutes"
            initialValue={0}
          >
            <InputNumber step={0.1} />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={loading}>
            Run Phase 3 Processing
          </Button>
        </Form>
      </Card>

      {result && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message={result.message}
          description={`Candidate event count: ${result.candidate_event_count}`}
        />
      )}

      {files.length > 0 && <OutputFileList cowId={cowId} files={files} />}
    </>
  );
}