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
  const [error, setError] = useState(null);

  const loadFiles = async (id) => {
    const response = await apiClient.get(`/files/${id}`);
    setFiles(response.data.files);
  };

  const onFinish = async (values) => {
    setLoading(true);
    setCowId(values.cow_id);
    setError(null);

    try {
      const response = await apiClient.post(`/process/phase3/${values.cow_id}`, null, {
        params: {
          patch_offset_minutes: values.patch_offset_minutes || 0,
          bolus_offset_minutes: values.bolus_offset_minutes || 0,
        },
      });

      setResult(response.data);
      await loadFiles(values.cow_id);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Analysis could not be completed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageIntro
        title="Phase 3 Processing"
        subtitle="Final analysis runs only after every flagged polarity section has been reviewed."
        bullets={[
          "Applies your saved keep, flip, or uncertain decisions without modifying raw data.",
          "Computes acceleration magnitude, gyroscope magnitude, and movement artifact score.",
          "Detects candidate contraction peaks using prominence-based peak detection.",
          "Creates 10-minute summaries for bolus synchronization.",
          "Regenerates statistics, bolus heatmaps, actograms, signal figures, and synchronized files.",
        ]}
      />

      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="Polarity approval is required before this step."
        description="Use Polarity Review first. The backend will keep this analysis locked while any detected section is pending. Candidate events remain exploratory, not confirmed contractions."
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
            Run Reviewed Analysis
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
      {error && <Alert type="error" showIcon style={{ marginBottom: 16 }} message="Analysis is not ready" description={error} />}

      {files.length > 0 && <OutputFileList cowId={cowId} files={files} />}
    </>
  );
}
