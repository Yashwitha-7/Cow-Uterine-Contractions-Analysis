import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";
import OutputFileList from "../components/OutputFileList";

const { Paragraph, Text } = Typography;

export default function ClockLabExportPage() {
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
      const response = await apiClient.post(`/export/clocklab/${values.cow_id}`);
      setResult(response.data);
      await loadFiles(values.cow_id);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageIntro
        title="ClockLab Export"
        subtitle="This page creates ClockLab-ready CSV and AWD files."
        bullets={[
          "AWD files are created as copies of simplified timestamp-value CSV files.",
          "CSV backup files are preserved.",
          "Bolus exports use 10-minute temperature values.",
          "Contraction exports use sampled-only 10-minute bins so device-off gaps are not treated as real zero values.",
        ]}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Run Phase 3 before generating ClockLab files."
        description={
          <Paragraph style={{ marginBottom: 0 }}>
            ClockLab export depends on files such as{" "}
            <Text code>bolus_preprocessed.csv</Text> and{" "}
            <Text code>contractions_10min_summary.csv</Text>.
          </Paragraph>
        }
      />

      <Card title="Generate ClockLab Files" style={{ marginBottom: 16 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="6263" />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={loading}>
            Generate ClockLab CSV and AWD Files
          </Button>
        </Form>
      </Card>

      {result && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message={result.message}
        />
      )}

      {files.length > 0 && <OutputFileList cowId={cowId} files={files} />}
    </>
  );
}