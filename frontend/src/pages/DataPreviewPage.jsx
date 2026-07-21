import { useState } from "react";
import { Button, Card, Form, Input, InputNumber, Select, Table, Typography, Alert } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";

const { Text } = Typography;

const DATASET_OPTIONS = [
  { value: "contractions", label: "Contractions processed" },
  { value: "contractions_timing_qc", label: "Contractions timing QC" },
  { value: "contractions_qc", label: "Contractions QC report" },
  { value: "bolus", label: "Bolus processed" },
  { value: "bolus_qc", label: "Bolus QC report" },
  { value: "contractions_preprocessed", label: "Contractions preprocessed" },
  { value: "contraction_events", label: "Candidate contraction events" },
  { value: "contractions_10min_summary", label: "Contractions 10-min summary" },
  { value: "bolus_preprocessed", label: "Bolus preprocessed" },
  { value: "merged_10min_all_bolus", label: "Merged 10-min all bolus" },
  { value: "merged_10min_overlap_only", label: "Merged 10-min overlap only" },
];

export default function DataPreviewPage() {
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const response = await apiClient.get(
        `/preview/${values.cow_id}/${values.data_type}`,
        {
          params: { n_rows: values.n_rows },
        }
      );
      setPreviewData(response.data);
    } finally {
      setLoading(false);
    }
  };

  const columns =
    previewData?.columns?.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      render: (value) => String(value ?? ""),
    })) || [];

  return (
    <>
      <PageIntro
        title="Processed Data Preview"
        subtitle="This page lets you inspect generated CSV files before downloading or using them for analysis."
        bullets={[
          "Use timing QC to check sample periods, gaps, and partial files.",
          "Use preprocessed contractions to inspect baseline correction, movement score, and flat-signal flags.",
          "Use merged overlap-only data for bolus-contraction comparison.",
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="6263" />
          </Form.Item>

          <Form.Item
            label="Dataset to preview"
            name="data_type"
            rules={[{ required: true, message: "Select dataset" }]}
          >
            <Select options={DATASET_OPTIONS} />
          </Form.Item>

          <Form.Item label="Number of rows" name="n_rows" initialValue={50}>
            <InputNumber min={5} max={500} />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={loading}>
            Preview Data
          </Button>
        </Form>
      </Card>

      {previewData && (
        <>
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
            message={`Loaded ${previewData.row_count} rows from ${previewData.data_type}`}
            description={<Text code>{previewData.file_path}</Text>}
          />

          <Card title="Preview">
            <Table
              rowKey={(_, index) => index}
              columns={columns}
              dataSource={previewData.preview}
              scroll={{ x: true }}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </>
      )}
    </>
  );
}