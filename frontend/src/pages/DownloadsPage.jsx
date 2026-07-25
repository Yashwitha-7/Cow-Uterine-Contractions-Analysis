import { useState } from "react";
import { Button, Card, Form, Input, Alert } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";
import OutputFileList from "../components/OutputFileList";

export default function DownloadsPage() {
  const [loading, setLoading] = useState(false);
  const [cowId, setCowId] = useState("");
  const [files, setFiles] = useState([]);

  const onFinish = async (values) => {
    setLoading(true);
    setCowId(values.cow_id);

    try {
      const response = await apiClient.get(`/files/${values.cow_id}`);
      setFiles(response.data.files || []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageIntro
        title="Downloads"
        subtitle="This page lists all generated files for a cow and lets you download them from the local processed-data folder."
        bullets={[
          "Files are grouped by phase in the table.",
          "Generated files remain saved locally under data/processed/cow_<id>/.",
          "ClockLab CSV and AWD files appear after running ClockLab export.",
        ]}
      />

      <Card title="Find generated files" style={{ marginBottom: 16 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="6263" />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={loading}>
            List Files
          </Button>
        </Form>
      </Card>

      {files.length === 0 && cowId && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="No files found yet for this cow."
          description="Upload data and run Phase 3 processing first."
        />
      )}

      {files.length > 0 && <OutputFileList cowId={cowId} files={files} />}
    </>
  );
}