import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App", () => {
  it("renders the Bacara Academy application landmark", () => {
    render(<App />);

    expect(screen.getByRole("main")).toHaveAccessibleName("Bacara Academy");
  });
});
