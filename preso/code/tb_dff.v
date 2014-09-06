module tb_dff;

reg resetn;
reg en;
wire q;
reg d;
reg clk;

initial begin
    $from_myhdl(
        resetn,
        en,
        d,
        clk
    );
    $to_myhdl(
        q
    );
end

dff dut(
    resetn,
    en,
    q,
    d,
    clk
);

endmodule
