import { Layout, Typography } from "antd";

const { Header } = Layout;
const { Title, Text } = Typography;

export function AppHeader() {
  return (
    <Header
      style={{
        background: "#26382f",
        padding: "18px 32px",
        height: "auto",
        borderBottom: "1px solid #1d2b24",
      }}
    >
      <Title level={3} style={{ color: "#ffffff", margin: 0 }}>
        Hoffmann Lab Cow Monitoring Data Portal
      </Title>
      <Text style={{ color: "#d9e3dc" }}>
        Uterine contraction and bolus data ingestion system
      </Text>
    </Header>
  );
}