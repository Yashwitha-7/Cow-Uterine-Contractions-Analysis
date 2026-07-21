import { useEffect, useState } from "react";
import { Alert, Card, Table, Tag } from "antd";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";

export default function CowListPage() {
  const [cows, setCows] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadCows = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get("/cows");
      setCows(response.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCows();
  }, []);

  const columns = [
    { title: "Cow ID", dataIndex: "cow_id", key: "cow_id" },
    {
      title: "Contractions",
      dataIndex: "has_contractions",
      key: "has_contractions",
      render: (value) =>
        value ? <Tag color="green">Available</Tag> : <Tag>Missing</Tag>,
    },
    {
      title: "Bolus",
      dataIndex: "has_bolus",
      key: "has_bolus",
      render: (value) =>
        value ? <Tag color="green">Available</Tag> : <Tag>Missing</Tag>,
    },
    {
      title: "Contraction Rows",
      dataIndex: "contraction_rows",
      key: "contraction_rows",
    },
    {
      title: "Bolus Rows",
      dataIndex: "bolus_rows",
      key: "bolus_rows",
    },
    {
      title: "Calving Time",
      dataIndex: "calving_datetime",
      key: "calving_datetime",
      render: (value) => {
        if (!value) return "Not entered";
        return value.replace("T", " ").slice(0, 16);
      },
    },
    {
      title: "Notes",
      dataIndex: "notes",
      key: "notes",
    },
  ];

  return (
    <>
      <PageIntro
        title="Cow List"
        subtitle="This page summarizes which cows are currently available in the local database."
        bullets={[
          "Use this page after uploading data to confirm that the backend received the files.",
          "Contraction rows come from the processed TXT files.",
          "Bolus rows come from the processed Excel sheets.",
        ]}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="This page does not run analysis. It only summarizes what has already been uploaded and stored."
      />

      <Card>
        <Table
          rowKey="cow_id"
          columns={columns}
          dataSource={cows}
          loading={loading}
        />
      </Card>
    </>
  );
}