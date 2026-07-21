import { Button, Card, Table, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { buildDownloadUrl } from "../api/client";

const { Text } = Typography;

export default function OutputFileList({ cowId, files = [] }) {
  const columns = [
    {
      title: "Phase",
      dataIndex: "phase",
      key: "phase",
      width: 170,
      render: (value) => {
        const colorMap = {
          "Phase 1 / Phase 2": "green",
          "Phase 2": "gold",
          "Phase 3": "blue",
          "ClockLab Export": "purple",
          Visualization: "cyan",
        };

        return <Tag color={colorMap[value] || "default"}>{value}</Tag>;
      },
    },
    {
      title: "File",
      dataIndex: "file_name",
      key: "file_name",
      render: (value) => <Text code>{value}</Text>,
    },
    {
      title: "What this file means",
      dataIndex: "description",
      key: "description",
    },
    {
      title: "Size",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 120,
      render: (value) => `${(value / 1024).toFixed(1)} KB`,
    },
    {
      title: "Download",
      key: "download",
      width: 140,
      render: (_, record) => {
        let href = null;

        if (record.download_key) {
          href = buildDownloadUrl(`/download/${cowId}/${record.download_key}`);
        } else if (record.phase === "ClockLab Export") {
          href = buildDownloadUrl(
            `/download-clocklab/${cowId}/${encodeURIComponent(record.file_name)}`
          );
        } else if (record.phase === "Visualization") {
          href = buildDownloadUrl(
            `/download-figure/${cowId}/${encodeURIComponent(record.file_name)}`
          );
        }

        if (!href) {
          return null;
        }

        return (
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            href={href}
            target="_blank"
          >
            Download
          </Button>
        );
      },
    },
  ];

  return (
    <Card title="Generated Files">
      <Table
        rowKey={(record) => record.file_name}
        columns={columns}
        dataSource={files}
        pagination={{ pageSize: 8 }}
      />
    </Card>
  );
}