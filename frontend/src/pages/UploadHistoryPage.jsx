import { useEffect, useState } from "react";
import { Card, Table, Typography } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";

const { Text } = Typography;

export default function UploadHistoryPage() {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadUploads = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get("/uploads");
      setUploads(response.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUploads();
  }, []);

  const columns = [
    { title: "Upload ID", dataIndex: "id", key: "id", width: 100 },
    { title: "Cow ID", dataIndex: "cow_id", key: "cow_id", width: 100 },
    { title: "Data Type", dataIndex: "data_type", key: "data_type" },
    { title: "File Count", dataIndex: "file_count", key: "file_count" },
    { title: "Row Count", dataIndex: "row_count", key: "row_count" },
    {
      title: "Processed File",
      dataIndex: "processed_file_path",
      key: "processed_file_path",
      render: (value) => <Text code>{value || "Not available"}</Text>,
    },
    { title: "Created At", dataIndex: "created_at", key: "created_at" },
  ];

  return (
    <>
      <PageIntro
        title="Upload History"
        subtitle="This page tracks every upload batch processed by the local app."
        bullets={[
          "Use this page for traceability.",
          "Each upload batch records cow ID, data type, file count, row count, and processed output path.",
          "Duplicate files are skipped using SHA256 file hashing.",
        ]}
      />

      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={uploads}
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </>
  );
}