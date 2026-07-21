import { useEffect, useState } from "react";
import { Alert, Card, Table, Tag } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";

export default function QCLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get("/qc-logs");
      setLogs(response.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const columns = [
    { title: "Cow ID", dataIndex: "cow_id", key: "cow_id", width: 100 },
    { title: "Data Type", dataIndex: "data_type", key: "data_type" },
    { title: "Source File", dataIndex: "source_file", key: "source_file" },
    {
      title: "Severity",
      dataIndex: "severity",
      key: "severity",
      render: (value) => <Tag color="orange">{value}</Tag>,
    },
    { title: "Issue Type", dataIndex: "issue_type", key: "issue_type" },
    { title: "Message", dataIndex: "message", key: "message" },
    { title: "Created At", dataIndex: "created_at", key: "created_at" },
  ];

  return (
    <>
      <PageIntro
        title="QC Logs"
        subtitle="This page shows quality-control warnings from Phase 2."
        bullets={[
          "QC warnings do not delete data.",
          "They flag files that may need manual review.",
          "Examples include partial files, device-off gaps, flat/stuck strain, missing values, and unexpected movement flags.",
        ]}
      />

      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="QC logs are review flags, not automatic rejection labels."
      />

      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={logs}
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </>
  );
}