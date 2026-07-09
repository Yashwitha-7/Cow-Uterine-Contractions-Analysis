import { Card, Form, Input, Select, Button, Typography } from "antd";

const { Title, Paragraph } = Typography;

export function DownloadPage() {
  const onFinish = ({ cowId, dataType }) => {
    const url = `http://127.0.0.1:8000/api/download/${cowId}/${dataType}`;
    window.open(url, "_blank");
  };

  return (
    <Card
      style={{
        maxWidth: 720,
        margin: "32px auto",
        borderRadius: 12,
      }}
    >
      <Title level={3}>Download Processed Data</Title>
      <Paragraph>
        Download standardized processed CSV files by cow ID and data type.
      </Paragraph>

      <Form layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Cow ID"
          name="cowId"
          rules={[{ required: true, message: "Please enter a cow ID." }]}
        >
          <Input placeholder="Example: 6263" />
        </Form.Item>

        <Form.Item
          label="Data Type"
          name="dataType"
          rules={[{ required: true, message: "Please select a data type." }]}
        >
          <Select
            options={[
              { label: "Contractions", value: "contractions" },
              { label: "Bolus", value: "bolus" },
            ]}
          />
        </Form.Item>

        <Button type="primary" htmlType="submit">
          Download CSV
        </Button>
      </Form>
    </Card>
  );
}