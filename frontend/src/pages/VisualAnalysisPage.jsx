import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Image,
  Input,
  Row,
  Space,
  Typography,
} from "antd";
import { EyeOutlined, PictureOutlined } from "@ant-design/icons";
import { apiClient, buildDownloadUrl } from "../api/client";
import PageIntro from "../components/PageIntro";
import OutputFileList from "../components/OutputFileList";

const { Paragraph, Text, Title } = Typography;

export default function VisualAnalysisPage() {
  const [loading, setLoading] = useState(false);
  const [cowId, setCowId] = useState("");
  const [result, setResult] = useState(null);
  const [files, setFiles] = useState([]);

  const loadFiles = async (id) => {
    const response = await apiClient.get(`/files/${id}`);
    setFiles(response.data.files || []);
  };

  const onFinish = async (values) => {
    setLoading(true);
    setCowId(values.cow_id);
    setResult(null);

    try {
      const response = await apiClient.post(`/visualizations/${values.cow_id}`);
      setResult(response.data);
      await loadFiles(values.cow_id);
    } finally {
      setLoading(false);
    }
  };

  const figureFiles = files.filter((item) => item.phase === "Visualization");

  return (
    <>
      <PageIntro
        title="Visual Analysis"
        subtitle="Generate actogram-style and signal-level figures from the Phase 3 contraction and bolus analysis files."
        bullets={[
          "Full corrected strain trace shows the orientation-corrected contraction signal across all recording days.",
          "Peak event timeline shows candidate contractions, movement-associated peaks, and bad-signal regions.",
          "Actogram heatmaps show contraction activity by date and time of day.",
          "Signal correction review compares raw strain, file-centered strain, and orientation-corrected strain.",
          "For cows with bolus data, overlay plots compare temperature and contraction activity.",
        ]}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="Run Phase 3 before generating visualizations"
        description="This page uses contractions_preprocessed.csv, contraction_events.csv, and contractions_10min_summary.csv. If bolus Phase 3 files exist, bolus figures will also be created."
      />

      <Card title="Generate Visualizations" style={{ marginBottom: 16 }}>
        <Paragraph>
          Figures will be saved automatically under{" "}
          <Text code>data/processed/cow_&lt;id&gt;/figures/</Text> and will
          appear in the Downloads page.
        </Paragraph>

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="Example: 6263" />
          </Form.Item>

          <Space>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              icon={<PictureOutlined />}
            >
              Generate Figures
            </Button>
          </Space>
        </Form>
      </Card>

      {result && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          title={result.message}
          description={`Generated ${result.figure_count} figure(s) for cow ${result.cow_id}.`}
        />
      )}

      {figureFiles.length > 0 && (
        <Card title="Figure Preview" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            {figureFiles.map((file) => (
              <Col xs={24} md={12} key={file.file_name}>
                <Card
                  size="small"
                  title={
                    <span>
                      <EyeOutlined /> {file.file_name}
                    </span>
                  }
                >
                  <Paragraph>{file.description}</Paragraph>
                  <Image
                    src={buildDownloadUrl(
                      `/download-figure/${cowId}/${encodeURIComponent(
                        file.file_name
                      )}`
                    )}
                    alt={file.file_name}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {files.length > 0 && <OutputFileList cowId={cowId} files={files} />}
    </>
  );
}